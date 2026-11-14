"""Deterministic mock LLM that can emit invalid then corrected tool payloads."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from strict_tool_router.llm.base import LLMProvider, Message, ToolProposal, ToolSchema


class MockLLMProvider(LLMProvider):
    """
    Schema-demo mock with controllable failure modes.

    Modes (set via constructor or inferred from the latest user message):
    - ``bad_then_good`` — first proposal violates the schema; after a validation
      error is fed back, the next proposal is correct (proves retry).
    - ``always_bad`` — keeps emitting invalid payloads (proves rejection).
    - ``always_good`` — emits a valid payload on the first try.
    """

    name = "mock"

    def __init__(
        self,
        *,
        latency_ms: float = 5.0,
        mode: str = "bad_then_good",
        call_count: int | None = None,
    ) -> None:
        self.latency_ms = latency_ms
        self.mode = mode
        self._calls = 0 if call_count is None else call_count

    async def propose_tool_args(
        self,
        messages: list[Message],
        *,
        tool: ToolSchema,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> ToolProposal:
        await asyncio.sleep(self.latency_ms / 1000.0)
        mode = self._resolve_mode(messages)
        self._calls += 1
        has_validation_error = any(
            m.role == "user" and "VALIDATION_ERROR" in m.content for m in messages
        )

        if mode == "always_good" or (mode == "bad_then_good" and has_validation_error):
            args = self._valid_args(tool, messages)
        elif mode == "always_bad" or (mode == "bad_then_good" and not has_validation_error):
            args = self._invalid_args(tool)
        else:
            args = self._valid_args(tool, messages)

        return ToolProposal(
            name=tool.name,
            arguments=args,
            raw_text=json.dumps(args),
        )

    def _resolve_mode(self, messages: list[Message]) -> str:
        blob = " ".join(m.content for m in messages if m.role == "user").lower()
        if "always_bad" in blob or "mode=always_bad" in blob:
            return "always_bad"
        if "always_good" in blob or "mode=always_good" in blob:
            return "always_good"
        if "bad_then_good" in blob or "mode=bad_then_good" in blob:
            return "bad_then_good"
        return self.mode

    def _invalid_args(self, tool: ToolSchema) -> dict[str, Any]:
        """Deliberately wrong types / missing required fields for the demo tools."""
        if tool.name == "schedule_meeting":
            return {
                # attendees must be a list of emails; title required; duration int
                "title": "",
                "attendees": "not-a-list",
                "duration_minutes": "thirty",
                "priority": "urgent",  # not in enum
            }
        if tool.name == "transfer_funds":
            return {
                "from_account": "checking",
                "to_account": "checking",  # same account — will fail custom validator
                "amount": -50,
                "currency": "usd",  # must be uppercase ISO
            }
        if tool.name == "search_docs":
            return {
                "query": "",
                "limit": 999,
                "tags": "should-be-list",
            }
        # Generic: empty object usually fails required fields
        return {"__broken": True}

    def _valid_args(self, tool: ToolSchema, messages: list[Message]) -> dict[str, Any]:
        prompt = next((m.content for m in reversed(messages) if m.role == "user"), "")
        if tool.name == "schedule_meeting":
            title = _extract(r"title[=:]\s*([^\n;]+)", prompt) or "Sprint planning"
            return {
                "title": title.strip()[:120],
                "attendees": ["alice@example.com", "bob@example.com"],
                "duration_minutes": 30,
                "priority": "normal",
            }
        if tool.name == "transfer_funds":
            return {
                "from_account": "checking",
                "to_account": "savings",
                "amount": 25.50,
                "currency": "USD",
            }
        if tool.name == "search_docs":
            query = _extract(r"query[=:]\s*([^\n;]+)", prompt) or "pydantic validation"
            return {
                "query": query.strip()[:200],
                "limit": 5,
                "tags": ["agents", "tools"],
            }
        # Fall back to empty object — registry should only expose known tools
        return {}


def _extract(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1) if match else None
