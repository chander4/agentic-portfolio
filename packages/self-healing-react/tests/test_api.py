"""FastAPI surface for Self-Healing ReAct."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from self_healing_react.agent import SelfHealingReActAgent
from self_healing_react.config import Settings
from self_healing_react.llm.mock import MockLLMProvider
from self_healing_react.main import create_app


@pytest.fixture
def app():
    agent = SelfHealingReActAgent(
        settings=Settings(llm_provider="mock", max_heals=3),
        llm=MockLLMProvider(mode="always_ok", latency_ms=0.0),
    )
    return create_app(agent=agent)


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
    assert "compile_python" in names
    assert "eval_math" in names


@pytest.mark.asyncio
async def test_run_always_ok(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/run",
            json={"goal": "mode=always_ok; Compile result=42."},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["heals_used"] == 0


@pytest.mark.asyncio
async def test_demo_heal_fail_then_heal(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/demo/heal",
            json={"scenario": "fail_then_heal"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["heals_used"] == 1
    assert body["heals"][0]["healed"] is True
