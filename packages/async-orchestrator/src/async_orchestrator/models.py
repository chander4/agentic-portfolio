"""API and domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    name: str
    ok: bool
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class AgentStep(BaseModel):
    role: str  # system | user | assistant | tool
    content: str
    tool_calls: list[ToolCallResult] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utcnow)


class AgentTaskCreate(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    tools: list[str] = Field(
        default_factory=lambda: ["echo", "sleep", "fail"],
        description="Tool names the agent may invoke",
    )
    max_steps: int = Field(default=4, ge=1, le=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    prompt: str
    tools: list[str]
    max_steps: int = 4
    status: TaskStatus = TaskStatus.PENDING
    steps: list[AgentStep] = Field(default_factory=list)
    result: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float | None = None


class AgentTaskSummary(BaseModel):
    id: str
    status: TaskStatus
    prompt: str
    result: str | None = None
    error: str | None = None
    duration_ms: float | None = None
    created_at: datetime


class BatchCreate(BaseModel):
    tasks: list[AgentTaskCreate] = Field(..., min_length=1, max_length=500)


class BatchResult(BaseModel):
    submitted: int
    task_ids: list[str]


class OrchestratorStats(BaseModel):
    active: int
    completed: int
    failed: int
    pending: int
    max_concurrent: int
    provider: str
