"""API and domain models for schema-strict tool routing."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class RouteStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"  # exhausted retries still invalid


class ValidationAttempt(BaseModel):
    """One validate → (optional) retry cycle against a proposed tool payload."""

    attempt: int
    arguments: dict[str, Any]
    valid: bool
    error_trace: str | None = None


class RouteRequest(BaseModel):
    """Ask the router to produce a validated tool call for ``tool`` from ``prompt``."""

    prompt: str = Field(..., min_length=1, max_length=8000)
    tool: str = Field(..., min_length=1, description="Registered tool name")
    max_retries: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Override Settings.max_retries when set",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tool: str
    status: RouteStatus
    prompt: str
    arguments: dict[str, Any] | None = None
    tool_result: Any = None
    attempts: list[ValidationAttempt] = Field(default_factory=list)
    retries_used: int = 0
    error: str | None = None
    provider: str
    created_at: datetime = Field(default_factory=utcnow)
    duration_ms: float = 0.0


class DemoRequest(BaseModel):
    """Force the mock LLM into a bad-then-good trajectory for the hiring demo."""

    scenario: str = Field(
        default="bad_then_good",
        description="bad_then_good | always_bad | always_good",
    )
    tool: str = "schedule_meeting"


class ToolInfo(BaseModel):
    name: str
    description: str
    json_schema: dict[str, Any]
