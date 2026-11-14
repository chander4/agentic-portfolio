"""Pydantic schemas reject bad tool arguments."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from strict_tool_router.registry import ToolRegistry
from strict_tool_router.schemas import ScheduleMeetingArgs, TransferFundsArgs


def test_schedule_meeting_rejects_bad_types() -> None:
    with pytest.raises(ValidationError) as exc:
        ScheduleMeetingArgs.model_validate(
            {
                "title": "",
                "attendees": "not-a-list",
                "duration_minutes": "thirty",
                "priority": "urgent",
            }
        )
    text = str(exc.value)
    assert "attendees" in text or "duration" in text or "title" in text


def test_schedule_meeting_accepts_valid() -> None:
    args = ScheduleMeetingArgs.model_validate(
        {
            "title": "Sprint planning",
            "attendees": ["alice@example.com"],
            "duration_minutes": 30,
            "priority": "normal",
        }
    )
    assert args.title == "Sprint planning"
    assert args.duration_minutes == 30


def test_transfer_funds_rejects_same_account_and_negative() -> None:
    with pytest.raises(ValidationError):
        TransferFundsArgs.model_validate(
            {
                "from_account": "checking",
                "to_account": "checking",
                "amount": -50,
                "currency": "usd",
            }
        )


def test_registry_format_validation_error_includes_trace() -> None:
    registry = ToolRegistry()
    tool = registry.require("schedule_meeting")
    try:
        tool.validate({"title": "", "attendees": [], "duration_minutes": 1})
    except ValidationError as exc:
        trace = tool.format_validation_error(exc)
        assert "VALIDATION_ERROR" in trace
        assert "schedule_meeting" in trace
        assert "Return a corrected JSON object" in trace
    else:
        pytest.fail("expected ValidationError")
