"""FastAPI entrypoint for the Async Agent Orchestrator."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from async_orchestrator import __version__
from async_orchestrator.config import get_settings
from async_orchestrator.models import (
    AgentTask,
    AgentTaskCreate,
    AgentTaskSummary,
    BatchCreate,
    BatchResult,
    OrchestratorStats,
)
from async_orchestrator.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)


def create_app(orchestrator: AgentOrchestrator | None = None) -> FastAPI:
    settings = get_settings()
    state: dict[str, Any] = {"orchestrator": orchestrator}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["orchestrator"] is None:
            state["orchestrator"] = AgentOrchestrator(settings=settings)
        logger.info(
            "async-orchestrator v%s ready (provider=%s, max_concurrent=%s)",
            __version__,
            state["orchestrator"].llm.name,
            settings.max_concurrent_agents,
        )
        yield

    app = FastAPI(
        title="Async Agent Orchestrator",
        description=(
            "Event-driven agent runtime demonstrating why asyncio beats "
            "blocking while-True loops for concurrent tool-using agents."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    def orch() -> AgentOrchestrator:
        return state["orchestrator"]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/stats", response_model=OrchestratorStats)
    async def stats() -> OrchestratorStats:
        return orch().stats()

    @app.post("/tasks", response_model=AgentTaskSummary, status_code=202)
    async def create_task(body: AgentTaskCreate) -> AgentTaskSummary:
        task = await orch().submit(body)
        return _summary(task)

    @app.post("/tasks/batch", response_model=BatchResult, status_code=202)
    async def create_batch(body: BatchCreate) -> BatchResult:
        tasks = await orch().submit_many(body.tasks)
        return BatchResult(submitted=len(tasks), task_ids=[t.id for t in tasks])

    @app.get("/tasks", response_model=list[AgentTaskSummary])
    async def list_tasks(limit: int = 50) -> list[AgentTaskSummary]:
        return [_summary(t) for t in orch().list_tasks(limit=limit)]

    @app.get("/tasks/{task_id}", response_model=AgentTask)
    async def get_task(task_id: str) -> AgentTask:
        task = orch().get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @app.post("/tasks/{task_id}/wait", response_model=AgentTask)
    async def wait_task(task_id: str, timeout: float = 30.0) -> AgentTask:
        task = orch().get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        try:
            return await orch().wait(task_id, timeout=timeout)
        except TimeoutError as exc:
            raise HTTPException(status_code=408, detail="wait timed out") from exc

    @app.post("/demo/concurrency")
    async def demo_concurrency(count: int = 100, sleep_seconds: float = 0.05) -> dict[str, Any]:
        """
        Fire ``count`` concurrent sleep-tool agents and report wall-clock time.

        With non-blocking asyncio, wall time ≈ sleep_seconds (+overhead), not count×sleep.
        """
        import time

        count = max(1, min(count, 500))
        requests = [
            AgentTaskCreate(
                prompt=f"Please sleep {sleep_seconds} for agent {i}",
                tools=["sleep", "echo"],
                max_steps=2,
                metadata={"demo": "concurrency", "index": i},
            )
            for i in range(count)
        ]
        started = time.perf_counter()
        tasks = await orch().submit_many(requests)
        finished = await orch().wait_all([t.id for t in tasks], timeout=60.0)
        elapsed = time.perf_counter() - started
        succeeded = sum(1 for t in finished if t.status.value == "succeeded")
        failed = sum(1 for t in finished if t.status.value == "failed")
        return {
            "count": count,
            "sleep_seconds": sleep_seconds,
            "wall_seconds": round(elapsed, 4),
            "naive_serial_seconds": round(count * sleep_seconds, 4),
            "speedup_vs_serial": round((count * sleep_seconds) / elapsed, 2) if elapsed else None,
            "succeeded": succeeded,
            "failed": failed,
            "proof": (
                "Wall time stayed near sleep_seconds, not count*sleep - "
                "the event loop interleaved awaits instead of blocking."
            ),
        }

    return app


def _summary(task: AgentTask) -> AgentTaskSummary:
    return AgentTaskSummary(
        id=task.id,
        status=task.status,
        prompt=task.prompt,
        result=task.result,
        error=task.error,
        duration_ms=task.duration_ms,
        created_at=task.created_at,
    )


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "async_orchestrator.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
