"""API and domain models for context budget assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class SegmentKind(StrEnum):
    SYSTEM = "system"
    INSTRUCTION = "instruction"
    HISTORY = "history"
    RETRIEVAL = "retrieval"
    TOOL_SCHEMA = "tool_schema"
    USER = "user"
    OTHER = "other"


class Segment(BaseModel):
    """One packable unit of context with an explicit priority (lower = keep first)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: SegmentKind = SegmentKind.OTHER
    content: str = Field(..., min_length=0)
    priority: int = Field(
        default=100,
        description="Lower numbers are packed first (0 = must-keep).",
    )
    sticky: bool = Field(
        default=False,
        description="If true, never drop entirely — truncate instead when over budget.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class SegmentDecision(StrEnum):
    INCLUDED = "included"
    TRUNCATED = "truncated"
    DROPPED = "dropped"
    SUMMARIZED = "summarized"


class PackedSegment(BaseModel):
    id: str
    kind: SegmentKind
    priority: int
    decision: SegmentDecision
    original_tokens: int
    packed_tokens: int
    content: str
    note: str | None = None


class AssembleRequest(BaseModel):
    segments: list[Segment] = Field(..., min_length=1)
    budget_tokens: int | None = Field(default=None, ge=1, le=200_000)
    allow_summarize: bool = Field(
        default=False,
        description="When true, oversize sticky/low-priority segments may be summarized via LLM.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssembledContext(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    budget_tokens: int
    used_tokens: int
    leftover_tokens: int
    packed: list[PackedSegment]
    prompt_text: str
    dropped_ids: list[str] = Field(default_factory=list)
    provider: str = "none"
    created_at: datetime = Field(default_factory=utcnow)
    duration_ms: float = 0.0


class DemoRequest(BaseModel):
    scenario: str = Field(
        default="overflow_drop_low_priority",
        description=(
            "overflow_drop_low_priority | truncate_sticky | fits_under_budget | summarize_overflow"
        ),
    )
    budget_tokens: int = Field(default=80, ge=8, le=10_000)
