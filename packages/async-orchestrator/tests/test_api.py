"""FastAPI surface tests."""

from __future__ import annotations

import pytest
from async_orchestrator.config import Settings
from async_orchestrator.llm.mock import MockLLMProvider
from async_orchestrator.main import create_app
from async_orchestrator.orchestrator import AgentOrchestrator
from async_orchestrator.tools.registry import ToolRegistry
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    orch = AgentOrchestrator(
        llm=MockLLMProvider(latency_ms=1.0),
        tools=ToolRegistry(),
        settings=Settings(llm_provider="mock"),
    )
    return create_app(orchestrator=orch)


@pytest.mark.asyncio
async def test_health(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_submit_and_wait(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/tasks",
            json={"prompt": "echo hello world", "tools": ["echo"], "max_steps": 2},
        )
        assert created.status_code == 202
        task_id = created.json()["id"]

        waited = await client.post(f"/tasks/{task_id}/wait", params={"timeout": 10})
        assert waited.status_code == 200
        body = waited.json()
        assert body["status"] == "succeeded"
        assert body["result"]


@pytest.mark.asyncio
async def test_batch_and_demo(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        batch = await client.post(
            "/tasks/batch",
            json={
                "tasks": [
                    {"prompt": "echo a", "tools": ["echo"], "max_steps": 2},
                    {"prompt": "echo b", "tools": ["echo"], "max_steps": 2},
                ]
            },
        )
        assert batch.status_code == 202
        assert batch.json()["submitted"] == 2

        demo = await client.post(
            "/demo/concurrency",
            params={"count": 25, "sleep_seconds": 0.02},
        )
        assert demo.status_code == 200
        payload = demo.json()
        assert payload["succeeded"] == 25
        assert payload["wall_seconds"] < payload["naive_serial_seconds"]
