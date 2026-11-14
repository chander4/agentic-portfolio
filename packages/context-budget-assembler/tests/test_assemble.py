"""Core packing: fit, drop low priority, truncate sticky, summarize."""

from __future__ import annotations

import pytest
from context_budget_assembler.assembler import ContextBudgetAssembler
from context_budget_assembler.config import Settings
from context_budget_assembler.demo_scenarios import build_scenario
from context_budget_assembler.llm.mock import MockLLMProvider
from context_budget_assembler.models import (
    AssembleRequest,
    Segment,
    SegmentDecision,
    SegmentKind,
)


@pytest.fixture
def assembler() -> ContextBudgetAssembler:
    return ContextBudgetAssembler(
        settings=Settings(llm_provider="mock", chars_per_token=4.0),
        llm=MockLLMProvider(latency_ms=0.0, chars_per_token=4.0),
    )


@pytest.mark.asyncio
async def test_fits_under_budget(assembler: ContextBudgetAssembler) -> None:
    result = await assembler.assemble(
        build_scenario("fits_under_budget", budget_tokens=200)
    )
    assert result.used_tokens <= result.budget_tokens
    assert result.dropped_ids == []
    assert all(p.decision == SegmentDecision.INCLUDED for p in result.packed)


@pytest.mark.asyncio
async def test_overflow_drops_low_priority(assembler: ContextBudgetAssembler) -> None:
    result = await assembler.assemble(
        build_scenario("overflow_drop_low_priority", budget_tokens=80)
    )
    assert result.used_tokens <= 80
    # Low-priority rag-lo should be dropped or truncated last
    by_id = {p.id: p for p in result.packed}
    assert by_id["sys"].decision == SegmentDecision.INCLUDED
    assert by_id["user"].decision == SegmentDecision.INCLUDED
    assert "rag-lo" in result.dropped_ids or by_id["rag-lo"].decision in {
        SegmentDecision.DROPPED,
        SegmentDecision.TRUNCATED,
    }
    # Higher-priority retrieval should survive when something must go
    assert by_id["rag-hi"].decision != SegmentDecision.DROPPED or by_id[
        "rag-lo"
    ].decision == SegmentDecision.DROPPED


@pytest.mark.asyncio
async def test_truncate_sticky(assembler: ContextBudgetAssembler) -> None:
    result = await assembler.assemble(
        build_scenario("truncate_sticky", budget_tokens=40)
    )
    by_id = {p.id: p for p in result.packed}
    assert by_id["rag"].decision == SegmentDecision.TRUNCATED
    assert by_id["rag"].packed_tokens <= 40
    assert by_id["rag"].content.endswith("…")
    assert result.used_tokens <= 40


@pytest.mark.asyncio
async def test_summarize_overflow(assembler: ContextBudgetAssembler) -> None:
    result = await assembler.assemble(
        build_scenario("summarize_overflow", budget_tokens=40)
    )
    by_id = {p.id: p for p in result.packed}
    assert by_id["hist"].decision == SegmentDecision.SUMMARIZED
    assert by_id["hist"].content.startswith("[summary]")
    assert result.provider == "mock"
    assert result.used_tokens <= 40


@pytest.mark.asyncio
async def test_priority_order_keeps_must_have(assembler: ContextBudgetAssembler) -> None:
    request = AssembleRequest(
        budget_tokens=30,
        segments=[
            Segment(
                id="noise",
                kind=SegmentKind.RETRIEVAL,
                priority=90,
                content=("noise " * 40).strip(),
            ),
            Segment(
                id="must",
                kind=SegmentKind.SYSTEM,
                priority=0,
                sticky=True,
                content="MUST KEEP SYSTEM",
            ),
        ],
    )
    result = await assembler.assemble(request)
    by_id = {p.id: p for p in result.packed}
    assert by_id["must"].decision == SegmentDecision.INCLUDED
    assert by_id["must"].content == "MUST KEEP SYSTEM"
