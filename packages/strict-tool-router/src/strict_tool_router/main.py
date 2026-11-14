"""FastAPI entrypoint for the Strict Pydantic Tool Router."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from strict_tool_router import __version__
from strict_tool_router.config import get_settings
from strict_tool_router.llm.mock import MockLLMProvider
from strict_tool_router.models import DemoRequest, RouteRequest, RouteResult, ToolInfo
from strict_tool_router.router import StrictToolRouter

logger = logging.getLogger(__name__)


def create_app(router: StrictToolRouter | None = None) -> FastAPI:
    settings = get_settings()
    state: dict[str, Any] = {"router": router}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["router"] is None:
            state["router"] = StrictToolRouter(settings=settings)
        logger.info(
            "strict-tool-router v%s ready (provider=%s, max_retries=%s)",
            __version__,
            state["router"].llm.name,
            settings.max_retries,
        )
        yield

    app = FastAPI(
        title="Strict Pydantic Tool Router",
        description=(
            "Schema-first tool execution: LLM proposals are validated against "
            "Pydantic models; failures retry with the validation error trace."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    def get_router() -> StrictToolRouter:
        return state["router"]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/tools", response_model=list[ToolInfo])
    async def list_tools() -> list[ToolInfo]:
        return [
            ToolInfo(
                name=t.name,
                description=t.description,
                json_schema=t.json_schema(),
            )
            for t in get_router().registry.list_tools()
        ]

    @app.post("/route", response_model=RouteResult)
    async def route(body: RouteRequest) -> RouteResult:
        return await get_router().route(body)

    @app.post("/demo/retry", response_model=RouteResult)
    async def demo_retry(body: DemoRequest | None = None) -> RouteResult:
        """
        Hiring demo: mock LLM emits invalid args, then corrects after VALIDATION_ERROR.

        Uses an in-request MockLLMProvider so the demo is deterministic regardless
        of the process-wide LLM_PROVIDER setting.
        """
        body = body or DemoRequest()
        tool_name = body.tool
        if get_router().registry.get(tool_name) is None:
            raise HTTPException(status_code=404, detail=f"unknown tool: {tool_name}")

        demo_router = StrictToolRouter(
            settings=settings,
            llm=MockLLMProvider(mode=body.scenario, latency_ms=1.0),
            registry=get_router().registry,
        )
        prompt = (
            f"mode={body.scenario}; "
            f"Please call {tool_name} with appropriate arguments. "
            f"title=Architecture review"
        )
        return await demo_router.route(
            RouteRequest(prompt=prompt, tool=tool_name, max_retries=3)
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "strict_tool_router.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
