"""Self-healing ReAct loop: act → catch → parse error → rewrite → retry."""

from __future__ import annotations

import inspect
import json
import time
from typing import Any

from self_healing_react.config import Settings, get_settings
from self_healing_react.errors import parse_exception
from self_healing_react.llm.base import LLMProvider, Message, ToolSchema
from self_healing_react.llm.factory import create_llm_provider
from self_healing_react.models import (
    HealAttempt,
    RunRequest,
    RunResult,
    RunStatus,
    StepKind,
    TraceStep,
)
from self_healing_react.tools import ToolDefinition, ToolRegistry

_SYSTEM_PROMPT = """You are a ReAct agent with a self-healing loop.
Think step-by-step. Call ONE tool at a time with JSON arguments.
If you receive a HEAL_ERROR message, read the stack trace / compiler diagnostic,
rewrite the failing tool call arguments, and retry. Do not repeat the same broken payload.
When the goal is satisfied, return a final answer instead of another tool call.
"""


class SelfHealingReActAgent:
    """
    ReAct agent that treats tool failures as recoverable signals.

    Runtime exceptions (including ``compile()`` SyntaxErrors with lineno/offset)
    are parsed into a ``HEAL_ERROR`` trace, appended to the conversation, and
    the model is asked to rewrite the tool call — bounded by ``max_heals``.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        llm: LLMProvider | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or create_llm_provider(self.settings)
        self.registry = registry or ToolRegistry()

    async def run(self, request: RunRequest) -> RunResult:
        started = time.perf_counter()
        max_heals = (
            request.max_heals if request.max_heals is not None else self.settings.max_heals
        )
        max_steps = (
            request.max_steps if request.max_steps is not None else self.settings.max_steps
        )

        tools = [
            ToolSchema(name=t.name, description=t.description, parameters=t.parameters)
            for t in self.registry.list_tools()
        ]
        messages: list[Message] = [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(
                role="user",
                content=(
                    f"Goal:\n{request.goal}\n\n"
                    f"Available tools:\n{self.registry.schemas_for_prompt()}"
                ),
            ),
        ]

        steps: list[TraceStep] = []
        heals: list[HealAttempt] = []
        heals_used = 0
        step_idx = 0

        for _ in range(max_steps):
            action = await self.llm.propose_action(
                messages,
                tools=tools,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )

            if action.thought:
                steps.append(
                    TraceStep(index=step_idx, kind=StepKind.THOUGHT, content=action.thought)
                )
                step_idx += 1

            if action.final_answer:
                steps.append(
                    TraceStep(
                        index=step_idx,
                        kind=StepKind.FINAL,
                        content=action.final_answer,
                        ok=True,
                    )
                )
                return RunResult(
                    goal=request.goal,
                    status=RunStatus.SUCCEEDED,
                    answer=action.final_answer,
                    steps=steps,
                    heals=heals,
                    heals_used=heals_used,
                    provider=self.llm.name,
                    duration_ms=(time.perf_counter() - started) * 1000,
                )

            if not action.tool:
                return RunResult(
                    goal=request.goal,
                    status=RunStatus.FAILED,
                    steps=steps,
                    heals=heals,
                    heals_used=heals_used,
                    error="model returned neither tool nor final_answer",
                    provider=self.llm.name,
                    duration_ms=(time.perf_counter() - started) * 1000,
                )

            try:
                tool = self.registry.require(action.tool)
            except KeyError as exc:
                return RunResult(
                    goal=request.goal,
                    status=RunStatus.FAILED,
                    steps=steps,
                    heals=heals,
                    heals_used=heals_used,
                    error=str(exc),
                    provider=self.llm.name,
                    duration_ms=(time.perf_counter() - started) * 1000,
                )

            arguments = action.arguments if isinstance(action.arguments, dict) else {}
            steps.append(
                TraceStep(
                    index=step_idx,
                    kind=StepKind.ACTION,
                    content=f"{tool.name}({json.dumps(arguments)})",
                    tool=tool.name,
                    arguments=arguments,
                )
            )
            step_idx += 1

            try:
                result = await self._execute(tool, arguments)
            except Exception as exc:  # noqa: BLE001 — heal loop must catch tool failures
                parsed = parse_exception(exc)
                heal_msg = parsed.format_heal_message(tool=tool.name, arguments=arguments)
                heal = HealAttempt(
                    attempt=heals_used,
                    tool=tool.name,
                    arguments=arguments,
                    error_trace=heal_msg,
                    healed=False,
                )
                heals.append(heal)
                steps.append(
                    TraceStep(
                        index=step_idx,
                        kind=StepKind.HEAL,
                        content=heal_msg,
                        tool=tool.name,
                        arguments=arguments,
                        ok=False,
                        error_summary=f"{parsed.exception_type}: {parsed.message}",
                    )
                )
                step_idx += 1

                if heals_used >= max_heals:
                    return RunResult(
                        goal=request.goal,
                        status=RunStatus.FAILED,
                        steps=steps,
                        heals=heals,
                        heals_used=heals_used,
                        error=heal_msg,
                        provider=self.llm.name,
                        duration_ms=(time.perf_counter() - started) * 1000,
                    )

                heals_used += 1
                messages.append(
                    Message(
                        role="assistant",
                        content=json.dumps(
                            {
                                "thought": action.thought,
                                "tool": tool.name,
                                "arguments": arguments,
                            }
                        ),
                    )
                )
                messages.append(Message(role="user", content=heal_msg))
                continue

            observation = json.dumps(result, default=str)
            steps.append(
                TraceStep(
                    index=step_idx,
                    kind=StepKind.OBSERVATION,
                    content=observation,
                    tool=tool.name,
                    arguments=arguments,
                    ok=True,
                )
            )
            step_idx += 1

            # Mark the most recent heal (if any) as successfully rewritten
            if heals and not heals[-1].healed and heals[-1].tool == tool.name:
                heals[-1].healed = True
                heals[-1].rewritten_arguments = arguments

            messages.append(
                Message(
                    role="assistant",
                    content=json.dumps(
                        {
                            "thought": action.thought,
                            "tool": tool.name,
                            "arguments": arguments,
                        }
                    ),
                )
            )
            messages.append(Message(role="user", content=f"OBSERVATION: {observation}"))

        return RunResult(
            goal=request.goal,
            status=RunStatus.ABORTED,
            steps=steps,
            heals=heals,
            heals_used=heals_used,
            error=f"aborted after {max_steps} steps without a final answer",
            provider=self.llm.name,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    async def _execute(self, tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
        result = tool.handler(arguments)
        if inspect.isawaitable(result):
            return await result
        return result
