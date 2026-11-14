"""FastAPI entrypoint for the Self-Healing ReAct agent."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from self_healing_react import __version__
from self_healing_react.agent import SelfHealingReActAgent
from self_healing_react.config import get_settings
from self_healing_react.llm.mock import MockLLMProvider
from self_healing_react.models import DemoRequest, RunRequest, RunResult, ToolInfo

logger = logging.getLogger(__name__)


def create_app(agent: SelfHealingReActAgent | None = None) -> FastAPI:
    settings = get_settings()
    state: dict[str, Any] = {"agent": agent}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["agent"] is None:
            state["agent"] = SelfHealingReActAgent(settings=settings)
        logger.info(
            "self-healing-react v%s ready (provider=%s, max_heals=%s)",
            __version__,
            state["agent"].llm.name,
            settings.max_heals,
        )
        yield

    app = FastAPI(
        title="Self-Healing ReAct",
        description=(
            "ReAct agent that reads its own stack traces / compile() diagnostics, "
            "rewrites the failing tool call, and retries up to a bounded heal budget."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    def get_agent() -> SelfHealingReActAgent:
        return state["agent"]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/tools", response_model=list[ToolInfo])
    async def list_tools() -> list[ToolInfo]:
        return [
            ToolInfo(name=t.name, description=t.description, parameters=t.parameters)
            for t in get_agent().registry.list_tools()
        ]

    @app.post("/run", response_model=RunResult)
    async def run_agent(body: RunRequest) -> RunResult:
        return await get_agent().run(body)

    @app.post("/demo/heal", response_model=RunResult)
    async def demo_heal(body: DemoRequest | None = None) -> RunResult:
        """
        Hiring demo: mock LLM emits a broken compile_python call, then heals
        after reading the SyntaxError / stack trace.
        """
        body = body or DemoRequest()
        demo_agent = SelfHealingReActAgent(
            settings=settings,
            llm=MockLLMProvider(mode=body.scenario, latency_ms=1.0),
            registry=get_agent().registry,
        )
        goal = f"mode={body.scenario}; {body.goal}"
        return await demo_agent.run(RunRequest(goal=goal, max_heals=3, max_steps=6))

    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "self_healing_react.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
