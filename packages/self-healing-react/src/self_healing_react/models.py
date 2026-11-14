"""API and domain models for the self-healing ReAct loop."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"  # exhausted heals or unrecoverable
    ABORTED = "aborted"  # max steps without a final answer


class StepKind(StrEnum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    HEAL = "heal"
    FINAL = "final"


class TraceStep(BaseModel):
    """One element of the ReAct / heal trajectory."""

    index: int
    kind: StepKind
    content: str
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    ok: bool | None = None
    error_summary: str | None = None


class HealAttempt(BaseModel):
    """One failed tool execution and the rewrite that followed (if any)."""

    attempt: int
    tool: str
    arguments: dict[str, Any]
    error_trace: str
    healed: bool = False
    rewritten_arguments: dict[str, Any] | None = None


class RunRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=8000)
    max_heals: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Override Settings.max_heals when set",
    )
    max_steps: int | None = Field(default=None, ge=1, le=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    goal: str
    status: RunStatus
    answer: str | None = None
    steps: list[TraceStep] = Field(default_factory=list)
    heals: list[HealAttempt] = Field(default_factory=list)
    heals_used: int = 0
    error: str | None = None
    provider: str
    created_at: datetime = Field(default_factory=utcnow)
    duration_ms: float = 0.0


class DemoRequest(BaseModel):
    """Force the mock LLM into a fail-then-heal trajectory for the hiring demo."""

    scenario: str = Field(
        default="fail_then_heal",
        description="fail_then_heal | always_fail | always_ok",
    )
    goal: str = Field(
        default="Compile and run a tiny Python snippet that returns 42.",
        min_length=1,
        max_length=8000,
    )


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
