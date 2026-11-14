"""Pack prompt segments under a hard token budget by priority."""

from __future__ import annotations

import time

from context_budget_assembler.config import Settings, get_settings
from context_budget_assembler.llm.base import LLMProvider
from context_budget_assembler.llm.factory import create_llm_provider
from context_budget_assembler.models import (
    AssembledContext,
    AssembleRequest,
    PackedSegment,
    Segment,
    SegmentDecision,
    SegmentKind,
)
from context_budget_assembler.tokens import estimate_tokens, truncate_to_tokens

_KIND_ORDER = {
    SegmentKind.SYSTEM: 0,
    SegmentKind.INSTRUCTION: 1,
    SegmentKind.TOOL_SCHEMA: 2,
    SegmentKind.RETRIEVAL: 3,
    SegmentKind.HISTORY: 4,
    SegmentKind.USER: 5,
    SegmentKind.OTHER: 6,
}


class ContextBudgetAssembler:
    """
    Dynamic context packer.

    Segments are sorted by ascending ``priority`` (then sticky, then original order).
    The assembler includes as many as fit. Sticky segments that do not fit are
    truncated (or optionally summarized via the LLM). Non-sticky overflow is dropped.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or create_llm_provider(self.settings)

    async def assemble(self, request: AssembleRequest) -> AssembledContext:
        started = time.perf_counter()
        budget = request.budget_tokens or self.settings.default_budget_tokens
        cpt = self.settings.chars_per_token

        ordered = self._order(request.segments)
        remaining = budget
        packed: list[PackedSegment] = []
        dropped: list[str] = []

        for segment in ordered:
            original = estimate_tokens(segment.content, chars_per_token=cpt)
            if original == 0:
                packed.append(
                    PackedSegment(
                        id=segment.id,
                        kind=segment.kind,
                        priority=segment.priority,
                        decision=SegmentDecision.INCLUDED,
                        original_tokens=0,
                        packed_tokens=0,
                        content=segment.content,
                    )
                )
                continue

            if original <= remaining:
                packed.append(
                    PackedSegment(
                        id=segment.id,
                        kind=segment.kind,
                        priority=segment.priority,
                        decision=SegmentDecision.INCLUDED,
                        original_tokens=original,
                        packed_tokens=original,
                        content=segment.content,
                    )
                )
                remaining -= original
                continue

            # Does not fit fully
            if remaining <= 0 and not segment.sticky:
                dropped.append(segment.id)
                packed.append(
                    PackedSegment(
                        id=segment.id,
                        kind=segment.kind,
                        priority=segment.priority,
                        decision=SegmentDecision.DROPPED,
                        original_tokens=original,
                        packed_tokens=0,
                        content="",
                        note="dropped: budget exhausted",
                    )
                )
                continue

            if request.allow_summarize and remaining >= 8:
                summary = await self.llm.summarize(
                    segment.content,
                    target_tokens=remaining,
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                )
                summary = truncate_to_tokens(summary, remaining, chars_per_token=cpt)
                used = estimate_tokens(summary, chars_per_token=cpt)
                packed.append(
                    PackedSegment(
                        id=segment.id,
                        kind=segment.kind,
                        priority=segment.priority,
                        decision=SegmentDecision.SUMMARIZED,
                        original_tokens=original,
                        packed_tokens=used,
                        content=summary,
                        note=f"summarized by {self.llm.name}",
                    )
                )
                remaining -= used
                continue

            if remaining > 0:
                # Spend residual budget: truncate rather than waste leftover tokens.
                truncated = truncate_to_tokens(
                    segment.content, remaining, chars_per_token=cpt
                )
                used = estimate_tokens(truncated, chars_per_token=cpt)
                packed.append(
                    PackedSegment(
                        id=segment.id,
                        kind=segment.kind,
                        priority=segment.priority,
                        decision=SegmentDecision.TRUNCATED,
                        original_tokens=original,
                        packed_tokens=used,
                        content=truncated,
                        note="truncated to fit remaining budget",
                    )
                )
                remaining -= used
                continue

            dropped.append(segment.id)
            packed.append(
                PackedSegment(
                    id=segment.id,
                    kind=segment.kind,
                    priority=segment.priority,
                    decision=SegmentDecision.DROPPED,
                    original_tokens=original,
                    packed_tokens=0,
                    content="",
                    note="dropped: over budget",
                )
            )

        prompt_text = self._render_prompt(packed)
        used = budget - remaining
        return AssembledContext(
            budget_tokens=budget,
            used_tokens=used,
            leftover_tokens=remaining,
            packed=packed,
            prompt_text=prompt_text,
            dropped_ids=dropped,
            provider=self.llm.name if request.allow_summarize else "none",
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    def _order(self, segments: list[Segment]) -> list[Segment]:
        indexed = list(enumerate(segments))
        indexed.sort(key=lambda pair: (pair[1].priority, 0 if pair[1].sticky else 1, pair[0]))
        return [seg for _, seg in indexed]

    def _render_prompt(self, packed: list[PackedSegment]) -> str:
        visible = [p for p in packed if p.decision != SegmentDecision.DROPPED and p.content]
        visible.sort(key=lambda p: (_KIND_ORDER.get(p.kind, 99), p.priority))
        blocks: list[str] = []
        for item in visible:
            blocks.append(f"[{item.kind.value.upper()}]\n{item.content}")
        return "\n\n".join(blocks)
