"""FastAPI surface for Context Budget Assembler."""

from __future__ import annotations

import pytest
from context_budget_assembler.assembler import ContextBudgetAssembler
from context_budget_assembler.config import Settings
from context_budget_assembler.llm.mock import MockLLMProvider
from context_budget_assembler.main import create_app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    assembler = ContextBudgetAssembler(
        settings=Settings(llm_provider="mock", chars_per_token=4.0),
        llm=MockLLMProvider(latency_ms=0.0, chars_per_token=4.0),
    )
    return create_app(assembler=assembler)


@pytest.mark.asyncio
async def test_health(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_assemble_endpoint(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/assemble",
            json={
                "budget_tokens": 100,
                "segments": [
                    {
                        "id": "sys",
                        "kind": "system",
                        "priority": 0,
                        "sticky": True,
                        "content": "Be brief.",
                    },
                    {
                        "id": "user",
                        "kind": "user",
                        "priority": 10,
                        "content": "Hello",
                    },
                ],
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["used_tokens"] <= 100
    assert body["dropped_ids"] == []


@pytest.mark.asyncio
async def test_demo_pack(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/demo/pack",
            json={"scenario": "overflow_drop_low_priority", "budget_tokens": 80},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["budget_tokens"] == 80
    assert body["used_tokens"] <= 80
