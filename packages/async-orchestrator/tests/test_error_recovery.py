"""Graceful error recovery — tool failures must not crash the loop."""

from __future__ import annotations

import pytest
from async_orchestrator.config import Settings
from async_orchestrator.llm.mock import MockLLMProvider
from async_orchestrator.models import AgentTaskCreate, TaskStatus
from async_orchestrator.orchestrator import AgentOrchestrator
from async_orchestrator.tools.registry import ToolRegistry


@pytest.fixture
def orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(
        llm=MockLLMProvider(latency_ms=1.0),
        tools=ToolRegistry(),
        settings=Settings(llm_provider="mock", max_concurrent_agents=64),
    )


@pytest.mark.asyncio
async def test_failing_tool_does_not_crash_sibling_agents(
    orchestrator: AgentOrchestrator,
) -> None:
    mix = [
        AgentTaskCreate(prompt="please fail now", tools=["fail", "echo"], max_steps=3),
        AgentTaskCreate(prompt="echo healthy", tools=["echo"], max_steps=2),
        AgentTaskCreate(prompt="sleep 0.01", tools=["sleep", "echo"], max_steps=2),
    ] * 10  # 30 agents, 10 intentional failures

    tasks = await orchestrator.submit_many(mix)
    finished = await orchestrator.wait_all([t.id for t in tasks], timeout=20.0)

    assert len(finished) == 30
    # Event loop survived; every task reached a terminal state.
    assert all(t.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED} for t in finished)
    # Healthy echo/sleep agents should succeed.
    healthy = [t for t in finished if "fail" not in t.prompt.lower()]
    assert healthy
    assert all(t.status == TaskStatus.SUCCEEDED for t in healthy)


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_result_not_exception() -> None:
    registry = ToolRegistry()
    result = await registry.invoke("does_not_exist", {})
    assert result.ok is False
    assert "unknown tool" in (result.error or "")


@pytest.mark.asyncio
async def test_tool_exception_is_captured() -> None:
    registry = ToolRegistry()
    result = await registry.invoke("fail", {"message": "boom"})
    assert result.ok is False
    assert "boom" in (result.error or "")


@pytest.mark.asyncio
async def test_tool_timeout_is_captured() -> None:
    registry = ToolRegistry()
    result = await registry.invoke("sleep", {"seconds": 1.0}, timeout=0.05)
    assert result.ok is False
    assert "timed out" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_orchestrator_survives_llm_exception() -> None:
    class FlakyLLM(MockLLMProvider):
        def __init__(self) -> None:
            super().__init__(latency_ms=1.0)
            self.calls = 0

        async def complete(self, messages, *, tools=None, temperature=0.2, max_tokens=1024):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("provider blew up")
            return await super().complete(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens
            )

    orch = AgentOrchestrator(
        llm=FlakyLLM(),
        tools=ToolRegistry(),
        settings=Settings(llm_provider="mock"),
    )
    task = await orch.submit(AgentTaskCreate(prompt="anything", tools=["echo"]))
    finished = await orch.wait(task.id, timeout=5.0)
    assert finished.status == TaskStatus.FAILED
    assert "provider blew up" in (finished.error or "")

    # Same event loop / orchestrator accepts new work after the failure.
    ok = await orch.submit(AgentTaskCreate(prompt="echo recover", tools=["echo"]))
    ok = await orch.wait(ok.id, timeout=5.0)
    assert ok.status == TaskStatus.SUCCEEDED
