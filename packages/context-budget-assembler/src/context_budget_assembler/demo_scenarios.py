"""Deterministic segment sets for hiring demos and tests."""

from __future__ import annotations

from context_budget_assembler.models import AssembleRequest, Segment, SegmentKind


def build_scenario(name: str, *, budget_tokens: int) -> AssembleRequest:
    if name == "fits_under_budget":
        return AssembleRequest(
            budget_tokens=budget_tokens,
            segments=[
                Segment(
                    id="sys",
                    kind=SegmentKind.SYSTEM,
                    priority=0,
                    sticky=True,
                    content="You are a helpful ops copilot.",
                ),
                Segment(
                    id="user",
                    kind=SegmentKind.USER,
                    priority=10,
                    sticky=True,
                    content="Summarize last deploy.",
                ),
            ],
        )

    if name == "truncate_sticky":
        # Tiny budget forces truncation of a sticky retrieval blob.
        return AssembleRequest(
            budget_tokens=budget_tokens,
            segments=[
                Segment(
                    id="sys",
                    kind=SegmentKind.SYSTEM,
                    priority=0,
                    sticky=True,
                    content="System policy: be concise.",
                ),
                Segment(
                    id="rag",
                    kind=SegmentKind.RETRIEVAL,
                    priority=20,
                    sticky=True,
                    content=("RUNBOOK " * 80).strip(),
                ),
            ],
        )

    if name == "summarize_overflow":
        return AssembleRequest(
            budget_tokens=budget_tokens,
            allow_summarize=True,
            segments=[
                Segment(
                    id="sys",
                    kind=SegmentKind.SYSTEM,
                    priority=0,
                    sticky=True,
                    content="System: answer with facts only.",
                ),
                Segment(
                    id="hist",
                    kind=SegmentKind.HISTORY,
                    priority=40,
                    sticky=False,
                    content=("old turn about networking " * 40).strip(),
                ),
            ],
        )

    # Default: overflow_drop_low_priority
    return AssembleRequest(
        budget_tokens=budget_tokens,
        segments=[
            Segment(
                id="sys",
                kind=SegmentKind.SYSTEM,
                priority=0,
                sticky=True,
                content="You are an agent that respects token budgets.",
            ),
            Segment(
                id="tools",
                kind=SegmentKind.TOOL_SCHEMA,
                priority=5,
                sticky=True,
                content='{"tools":[{"name":"deploy","args":{"service":"string"}}]}',
            ),
            Segment(
                id="rag-hi",
                kind=SegmentKind.RETRIEVAL,
                priority=20,
                content="High-priority runbook: rollback via canary.",
            ),
            Segment(
                id="rag-lo",
                kind=SegmentKind.RETRIEVAL,
                priority=80,
                content=("Low-priority chatter from old tickets. " * 30).strip(),
            ),
            Segment(
                id="user",
                kind=SegmentKind.USER,
                priority=10,
                sticky=True,
                content="How do I roll back service payments?",
            ),
        ],
    )
