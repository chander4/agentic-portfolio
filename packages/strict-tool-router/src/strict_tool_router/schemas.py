"""Pydantic argument models — the hard schema gate for tool calls."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class ScheduleMeetingArgs(BaseModel):
    """Book a meeting — attendees must be emails; duration bounded."""

    title: str = Field(..., min_length=1, max_length=120)
    attendees: list[str] = Field(..., min_length=1, max_length=20)
    duration_minutes: Annotated[int, Field(ge=15, le=180)]
    priority: Priority = Priority.NORMAL

    @field_validator("attendees")
    @classmethod
    def attendees_are_emails(cls, value: list[str]) -> list[str]:
        bad = [a for a in value if not _EMAIL_RE.match(a)]
        if bad:
            raise ValueError(f"attendees must be email addresses; invalid: {bad}")
        return value


class TransferFundsArgs(BaseModel):
    """Move money between accounts — amount positive; currency ISO-4217 uppercase."""

    from_account: str = Field(..., min_length=1, max_length=64)
    to_account: str = Field(..., min_length=1, max_length=64)
    amount: Annotated[float, Field(gt=0, le=1_000_000)]
    currency: str = Field(..., min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise ValueError("currency must be a 3-letter uppercase ISO code (e.g. USD)")
        return value

    @model_validator(mode="after")
    def distinct_accounts(self) -> TransferFundsArgs:
        if self.from_account == self.to_account:
            raise ValueError("from_account and to_account must differ")
        return self


class SearchDocsArgs(BaseModel):
    """Search documentation — non-empty query; bounded limit."""

    query: str = Field(..., min_length=1, max_length=200)
    limit: Annotated[int, Field(ge=1, le=50)] = 10
    tags: list[str] = Field(default_factory=list, max_length=10)
