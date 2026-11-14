"""Fail once → heal → succeed; give up after max heals."""

from __future__ import annotations

import pytest
from self_healing_react.agent import SelfHealingReActAgent
from self_healing_react.config import Settings
from self_healing_react.llm.mock import MockLLMProvider
from self_healing_react.models import RunRequest, RunStatus, StepKind


@pytest.mark.asyncio
async def test_fail_once_then_heal_succeeds() -> None:
    agent = SelfHealingReActAgent(
        settings=Settings(llm_provider="mock", max_heals=3),
        llm=MockLLMProvider(mode="fail_then_heal", latency_ms=0.0),
    )
    result = await agent.run(
        RunRequest(
            goal="mode=fail_then_heal; Compile a Python snippet that sets result=42.",
            max_heals=3,
            max_steps=6,
        )
    )

    assert result.status == RunStatus.SUCCEEDED
    assert result.heals_used == 1
    assert len(result.heals) == 1
    assert result.heals[0].healed is True
    trace = result.heals[0].error_trace
    assert "SyntaxError" in trace or "HEAL_ERROR" in trace
    assert result.heals[0].rewritten_arguments is not None
    assert "result = 42" in result.heals[0].rewritten_arguments.get("source", "")
    assert result.answer is not None
    assert any(s.kind == StepKind.HEAL for s in result.steps)
    assert any(s.kind == StepKind.OBSERVATION and s.ok for s in result.steps)
    assert any(s.kind == StepKind.FINAL for s in result.steps)


@pytest.mark.asyncio
async def test_always_fail_gives_up_after_max_heals() -> None:
    agent = SelfHealingReActAgent(
        settings=Settings(llm_provider="mock", max_heals=2),
        llm=MockLLMProvider(mode="always_fail", latency_ms=0.0),
    )
    result = await agent.run(
        RunRequest(
            goal="mode=always_fail; Compile anything.",
            max_heals=2,
            max_steps=8,
        )
    )

    assert result.status == RunStatus.FAILED
    assert result.heals_used == 2
    assert len(result.heals) == 3  # initial failure + 2 heal retries that still fail
    assert all(not h.healed for h in result.heals)
    assert result.answer is None
    assert result.error and "HEAL_ERROR" in result.error


@pytest.mark.asyncio
async def test_always_ok_succeeds_without_heal() -> None:
    agent = SelfHealingReActAgent(
        settings=Settings(llm_provider="mock", max_heals=3),
        llm=MockLLMProvider(mode="always_ok", latency_ms=0.0),
    )
    result = await agent.run(
        RunRequest(goal="mode=always_ok; Compile result=42.", max_heals=3)
    )

    assert result.status == RunStatus.SUCCEEDED
    assert result.heals_used == 0
    assert result.heals == []
    assert not any(s.kind == StepKind.HEAL for s in result.steps)


@pytest.mark.asyncio
async def test_eval_math_zero_division_heals() -> None:
    agent = SelfHealingReActAgent(
        settings=Settings(llm_provider="mock", max_heals=3),
        llm=MockLLMProvider(mode="fail_then_heal", latency_ms=0.0),
    )
    result = await agent.run(
        RunRequest(
            goal="mode=fail_then_heal; Evaluate a math expression that multiplies 6*7.",
            max_heals=3,
        )
    )

    assert result.status == RunStatus.SUCCEEDED
    assert result.heals_used == 1
    assert "ZeroDivisionError" in result.heals[0].error_trace
