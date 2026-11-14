"""
Event-driven agent orchestrator.

Why this exists
---------------
A naive agent loop looks like::

    while True:
        response = llm.call(...)          # blocks
        result = tool.run(...)            # blocks
        ...

That serializes every agent behind one OS thread and collapses under load.
This orchestrator instead:

1. Caps concurrency with an ``asyncio.Semaphore``
2. Schedules each agent as an independent ``asyncio.Task``
3. Awaits LLM + tool I/O so the event loop can interleave 100+ agents
4. Isolates tool failures so one bad tool never kills the loop or siblings
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from async_orchestrator.config import Settings, get_settings
from async_orchestrator.llm.base import LLMProvider, Message, ToolSpec
from async_orchestrator.llm.factory import create_llm_provider
from async_orchestrator.models import (
    AgentStep,
    AgentTask,
    AgentTaskCreate,
    OrchestratorStats,
    TaskStatus,
    utcnow,
)
from async_orchestrator.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

TaskListener = Callable[[AgentTask], Awaitable[None] | None]


class AgentOrchestrator:
    def __init__(
        self,
        *,
        llm: LLMProvider | None = None,
        tools: ToolRegistry | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or create_llm_provider(self.settings)
        self.tools = tools or ToolRegistry()
        self._sem = asyncio.Semaphore(self.settings.max_concurrent_agents)
        self._tasks: dict[str, AgentTask] = {}
        self._running: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()
        self._listeners: list[TaskListener] = []

    def on_task_update(self, listener: TaskListener) -> None:
        self._listeners.append(listener)

    async def submit(self, request: AgentTaskCreate) -> AgentTask:
        task = AgentTask(
            prompt=request.prompt,
            tools=request.tools,
            max_steps=request.max_steps,
            metadata=request.metadata,
        )
        async with self._lock:
            self._tasks[task.id] = task
        runner = asyncio.create_task(self._run_guarded(task.id), name=f"agent-{task.id}")
        self._running[task.id] = runner
        runner.add_done_callback(lambda _t, tid=task.id: self._running.pop(tid, None))
        return task

    async def submit_many(self, requests: list[AgentTaskCreate]) -> list[AgentTask]:
        return list(await asyncio.gather(*(self.submit(r) for r in requests)))

    def get(self, task_id: str) -> AgentTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, *, limit: int = 100) -> list[AgentTask]:
        items = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return items[:limit]

    def stats(self) -> OrchestratorStats:
        statuses = [t.status for t in self._tasks.values()]
        return OrchestratorStats(
            active=sum(1 for s in statuses if s == TaskStatus.RUNNING),
            completed=sum(1 for s in statuses if s == TaskStatus.SUCCEEDED),
            failed=sum(1 for s in statuses if s == TaskStatus.FAILED),
            pending=sum(1 for s in statuses if s == TaskStatus.PENDING),
            max_concurrent=self.settings.max_concurrent_agents,
            provider=self.llm.name,
        )

    async def wait(self, task_id: str, *, timeout: float | None = None) -> AgentTask:
        runner = self._running.get(task_id)
        if runner is not None:
            await asyncio.wait_for(asyncio.shield(runner), timeout=timeout)
        task = self._tasks[task_id]
        return task

    async def wait_all(
        self, task_ids: list[str], *, timeout: float | None = None
    ) -> list[AgentTask]:
        await asyncio.wait_for(
            asyncio.gather(
                *(self.wait(tid) for tid in task_ids),
                return_exceptions=True,
            ),
            timeout=timeout,
        )
        return [self._tasks[tid] for tid in task_ids]

    async def _run_guarded(self, task_id: str) -> None:
        async with self._sem:
            task = self._tasks[task_id]
            task.status = TaskStatus.RUNNING
            task.started_at = utcnow()
            await self._notify(task)
            started = time.perf_counter()
            try:
                await asyncio.wait_for(
                    self._execute(task),
                    timeout=self.settings.agent_timeout_seconds,
                )
                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.SUCCEEDED
            except TimeoutError:
                task.status = TaskStatus.FAILED
                task.error = f"agent timed out after {self.settings.agent_timeout_seconds}s"
                logger.warning("agent %s timed out", task_id)
            except Exception as exc:  # noqa: BLE001 — isolate per-agent failures
                task.status = TaskStatus.FAILED
                task.error = f"{type(exc).__name__}: {exc}"
                logger.exception("agent %s failed", task_id)
            finally:
                task.finished_at = utcnow()
                task.duration_ms = (time.perf_counter() - started) * 1000
                await self._notify(task)

    async def _execute(self, task: AgentTask) -> None:
        tool_objs = self.tools.list_specs(task.tools)
        tool_specs = [
            ToolSpec(name=t.name, description=t.description, parameters=t.parameters)
            for t in tool_objs
        ]

        messages: list[Message] = [
            Message(
                role="system",
                content=(
                    "You are a concise agent. Use tools when helpful. "
                    "When finished, respond with a short final answer."
                ),
            ),
            Message(role="user", content=task.prompt),
        ]

        for _step in range(task.max_steps):
            response = await self.llm.complete(
                messages,
                tools=tool_specs or None,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )

            if response.tool_calls:
                tool_results = await self._run_tools(response.tool_calls)
                step = AgentStep(
                    role="assistant",
                    content=response.content or "tool_calls",
                    tool_calls=tool_results,
                )
                task.steps.append(step)

                # Feed tool outcomes back without raising — failures become context.
                for tr in tool_results:
                    payload = (
                        json.dumps(tr.result)
                        if tr.ok
                        else json.dumps({"error": tr.error})
                    )
                    messages.append(
                        Message(
                            role="tool",
                            content=f"{tr.name}: {payload}",
                        )
                    )
                continue

            # Final answer path
            task.steps.append(AgentStep(role="assistant", content=response.content))
            task.result = response.content
            task.status = TaskStatus.SUCCEEDED
            return

        task.result = task.steps[-1].content if task.steps else None
        task.status = TaskStatus.SUCCEEDED

    async def _run_tools(self, calls: list[dict[str, Any]]) -> list:
        """Run tool calls concurrently; each failure is captured, not raised."""

        async def _one(call: dict[str, Any]):
            name = str(call.get("name", ""))
            args = call.get("arguments") or {}
            if not isinstance(args, dict):
                args = {"value": args}
            return await self.tools.invoke(
                name,
                args,
                timeout=self.settings.tool_timeout_seconds,
            )

        return list(await asyncio.gather(*(_one(c) for c in calls)))

    async def _notify(self, task: AgentTask) -> None:
        for listener in self._listeners:
            try:
                result = listener(task)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001
                logger.exception("task listener failed")
