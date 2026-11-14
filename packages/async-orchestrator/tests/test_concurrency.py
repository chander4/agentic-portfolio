"""Concurrency proofs at meaningful scale (100+ agents)."""

from __future__ import annotations

import time

import pytest
from async_orchestrator.config import Settings
from async_orchestrator.llm.mock import MockLLMProvider
from async_orchestrator.models import AgentTaskCreate, TaskStatus
from async_orchestrator.orchestrator import AgentOrchestrator
from async_orchestrator.tools.builtins import BlockingAntiPatternTool
from async_orchestrator.tools.registry import ToolRegistry


@pytest.fixture
def orchestrator() -> AgentOrchestrator:
    settings = Settings(
        llm_provider="mock",
        max_concurrent_agents=256,
        agent_timeout_seconds=30.0,
        tool_timeout_seconds=5.0,
    )
    return AgentOrchestrator(
        llm=MockLLMProvider(latency_ms=2.0),
        tools=ToolRegistry(),
        settings=settings,
    )


@pytest.mark.asyncio
async def test_100_agents_complete_near_sleep_not_serial(orchestrator: AgentOrchestrator) -> None:
    """Wall time for 100 sleep agents must be << serial expectation."""
    n = 100
    sleep_s = 0.05
    requests = [
        AgentTaskCreate(
            prompt=f"Please sleep {sleep_s}",
            tools=["sleep", "echo"],
            max_steps=2,
        )
        for _ in range(n)
    ]

    started = time.perf_counter()
    tasks = await orchestrator.submit_many(requests)
    finished = await orchestrator.wait_all([t.id for t in tasks], timeout=30.0)
    elapsed = time.perf_counter() - started

    assert len(finished) == n
    assert all(t.status == TaskStatus.SUCCEEDED for t in finished)

    serial = n * sleep_s
    # Allow generous overhead for CI / Windows scheduling, but still prove concurrency.
    assert elapsed < serial * 0.45, (
        f"expected concurrent wall << serial ({serial:.2f}s), got {elapsed:.2f}s"
    )
    assert elapsed < 3.0


@pytest.mark.asyncio
async def test_blocking_tool_destroys_concurrency() -> None:
    """Control experiment: sync sleep inside 'async' tools serializes work."""
    registry = ToolRegistry()
    registry.register(BlockingAntiPatternTool())
    orch = AgentOrchestrator(
        llm=MockLLMProvider(latency_ms=1.0),
        tools=registry,
        settings=Settings(llm_provider="mock", max_concurrent_agents=256),
    )

    # Monkey-patch mock to always call blocking_sleep
    async def blocking_complete(messages, *, tools=None, temperature=0.2, max_tokens=1024):
        await __import__("asyncio").sleep(0.001)
        from async_orchestrator.llm.base import LLMResponse

        tool_msgs = [m for m in messages if m.role == "tool"]
        if tool_msgs:
            return LLMResponse(content="done after block")
        return LLMResponse(
            content="TOOL_CALL",
            tool_calls=[{"name": "blocking_sleep", "arguments": {"seconds": 0.05}}],
        )

    orch.llm.complete = blocking_complete  # type: ignore[method-assign]

    n = 20
    requests = [
        AgentTaskCreate(prompt="block me", tools=["blocking_sleep"], max_steps=2)
        for _ in range(n)
    ]
    started = time.perf_counter()
    tasks = await orch.submit_many(requests)
    await orch.wait_all([t.id for t in tasks], timeout=30.0)
    elapsed = time.perf_counter() - started

    # Blocking path should approach serial time (20 * 0.05 = 1.0s)
    assert elapsed >= 0.7, f"blocking path should serialize; got {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_stats_reflect_batch(orchestrator: AgentOrchestrator) -> None:
    requests = [
        AgentTaskCreate(prompt="echo hello", tools=["echo"], max_steps=2) for _ in range(10)
    ]
    tasks = await orchestrator.submit_many(requests)
    await orchestrator.wait_all([t.id for t in tasks])
    stats = orchestrator.stats()
    assert stats.completed == 10
    assert stats.failed == 0
    assert stats.provider == "mock"
