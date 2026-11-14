"""FastAPI entrypoint for the Context Budget Assembler."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from context_budget_assembler import __version__
from context_budget_assembler.assembler import ContextBudgetAssembler
from context_budget_assembler.config import get_settings
from context_budget_assembler.demo_scenarios import build_scenario
from context_budget_assembler.models import AssembledContext, AssembleRequest, DemoRequest

logger = logging.getLogger(__name__)


def create_app(assembler: ContextBudgetAssembler | None = None) -> FastAPI:
    settings = get_settings()
    state: dict[str, Any] = {"assembler": assembler}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["assembler"] is None:
            state["assembler"] = ContextBudgetAssembler(settings=settings)
        logger.info(
            "context-budget-assembler v%s ready (provider=%s, budget=%s)",
            __version__,
            state["assembler"].llm.name,
            settings.default_budget_tokens,
        )
        yield

    app = FastAPI(
        title="Dynamic Context Budget Assembler",
        description=(
            "Pack system / retrieval / history / tool segments under a hard token "
            "budget with priority ordering, truncation, and optional summarization."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    def get_assembler() -> ContextBudgetAssembler:
        return state["assembler"]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/assemble", response_model=AssembledContext)
    async def assemble(body: AssembleRequest) -> AssembledContext:
        return await get_assembler().assemble(body)

    @app.post("/demo/pack", response_model=AssembledContext)
    async def demo_pack(body: DemoRequest | None = None) -> AssembledContext:
        body = body or DemoRequest()
        request = build_scenario(body.scenario, budget_tokens=body.budget_tokens)
        return await get_assembler().assemble(request)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "context_budget_assembler.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
