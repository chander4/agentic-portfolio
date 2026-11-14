"""Router retries with validation error trace and succeeds on corrected payload."""

from __future__ import annotations

import pytest
from strict_tool_router.config import Settings
from strict_tool_router.llm.mock import MockLLMProvider
from strict_tool_router.models import RouteRequest, RouteStatus
from strict_tool_router.router import StrictToolRouter


@pytest.mark.asyncio
async def test_bad_then_good_retries_and_succeeds() -> None:
    router = StrictToolRouter(
        settings=Settings(llm_provider="mock", max_retries=3),
        llm=MockLLMProvider(mode="bad_then_good", latency_ms=0.0),
    )
    result = await router.route(
        RouteRequest(
            prompt="mode=bad_then_good; title=Architecture review",
            tool="schedule_meeting",
        )
    )

    assert result.status == RouteStatus.SUCCEEDED
    assert result.retries_used == 1
    assert len(result.attempts) == 2
    assert result.attempts[0].valid is False
    assert result.attempts[0].error_trace is not None
    assert "VALIDATION_ERROR" in result.attempts[0].error_trace
    assert result.attempts[1].valid is True
    assert result.arguments is not None
    assert result.arguments["title"]
    assert result.tool_result["scheduled"] is True


@pytest.mark.asyncio
async def test_always_bad_exhausts_retries_and_rejects() -> None:
    router = StrictToolRouter(
        settings=Settings(llm_provider="mock", max_retries=2),
        llm=MockLLMProvider(mode="always_bad", latency_ms=0.0),
    )
    result = await router.route(
        RouteRequest(
            prompt="mode=always_bad",
            tool="schedule_meeting",
            max_retries=2,
        )
    )

    assert result.status == RouteStatus.REJECTED
    assert result.retries_used == 2
    assert all(not a.valid for a in result.attempts)
    assert result.tool_result is None
    assert result.error and "VALIDATION_ERROR" in result.error


@pytest.mark.asyncio
async def test_always_good_succeeds_without_retry() -> None:
    router = StrictToolRouter(
        settings=Settings(llm_provider="mock", max_retries=3),
        llm=MockLLMProvider(mode="always_good", latency_ms=0.0),
    )
    result = await router.route(
        RouteRequest(prompt="mode=always_good; title=Sync", tool="schedule_meeting")
    )

    assert result.status == RouteStatus.SUCCEEDED
    assert result.retries_used == 0
    assert len(result.attempts) == 1
    assert result.attempts[0].valid is True


@pytest.mark.asyncio
async def test_unknown_tool_fails_closed() -> None:
    router = StrictToolRouter(
        settings=Settings(llm_provider="mock"),
        llm=MockLLMProvider(mode="always_good", latency_ms=0.0),
    )
    result = await router.route(RouteRequest(prompt="hi", tool="does_not_exist"))
    assert result.status == RouteStatus.FAILED
    assert "unknown tool" in (result.error or "")
