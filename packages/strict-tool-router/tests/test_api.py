"""FastAPI surface for the Strict Pydantic Tool Router."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from strict_tool_router.config import Settings
from strict_tool_router.llm.mock import MockLLMProvider
from strict_tool_router.main import create_app
from strict_tool_router.router import StrictToolRouter


@pytest.fixture
def app():
    router = StrictToolRouter(
        settings=Settings(llm_provider="mock", max_retries=3),
        llm=MockLLMProvider(mode="always_good", latency_ms=0.0),
    )
    return create_app(router=router)


@pytest.mark.asyncio
async def test_health(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_list_tools(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools")
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()}
    assert "schedule_meeting" in names
    assert "transfer_funds" in names


@pytest.mark.asyncio
async def test_route_always_good(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/route",
            json={
                "prompt": "mode=always_good; title=API sync",
                "tool": "schedule_meeting",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["retries_used"] == 0


@pytest.mark.asyncio
async def test_demo_retry_bad_then_good(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/demo/retry",
            json={"scenario": "bad_then_good", "tool": "schedule_meeting"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["retries_used"] == 1
    assert body["attempts"][0]["valid"] is False
    assert body["attempts"][1]["valid"] is True
