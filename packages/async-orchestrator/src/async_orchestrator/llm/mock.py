"""Deterministic mock LLM for demos and concurrency tests (no credentials)."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from async_orchestrator.llm.base import LLMProvider, LLMResponse, Message, ToolSpec


class MockLLMProvider(LLMProvider):
    """
    Lightweight planner that emits tool calls from prompt cues, then a final answer.

    Designed so tests can drive hundreds of concurrent completions without network I/O.
    Artificial latency is async (await asyncio.sleep) — never blocking.
    """

    name = "mock"

    def __init__(self, *, latency_ms: float = 5.0) -> None:
        self.latency_ms = latency_ms

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        await asyncio.sleep(self.latency_ms / 1000.0)

        tool_names = {t.name for t in (tools or [])}
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        last_assistant = next(
            (m.content for m in reversed(messages) if m.role == "assistant"),
            None,
        )
        tool_results = [m for m in messages if m.role == "tool"]

        # After tools have run, produce a final answer.
        if tool_results or (last_assistant and "TOOL_CALL" not in (last_assistant or "")):
            summary = tool_results[-1].content if tool_results else last_user
            return LLMResponse(
                content=f"Completed: {summary[:240]}",
                tool_calls=[],
            )

        # First turn: optionally emit a tool call based on prompt hints.
        calls = self._plan_tools(last_user, tool_names)
        if calls:
            return LLMResponse(
                content="TOOL_CALL",
                tool_calls=calls,
            )

        return LLMResponse(content=f"Echo: {last_user[:240]}")

    def _plan_tools(self, prompt: str, available: set[str]) -> list[dict[str, Any]]:
        lower = prompt.lower()
        calls: list[dict[str, Any]] = []

        if "sleep" in available and ("sleep" in lower or "wait" in lower):
            seconds = 0.01
            match = re.search(r"sleep\s+(\d+(?:\.\d+)?)", lower)
            if match:
                seconds = min(float(match.group(1)), 0.5)
            calls.append({"name": "sleep", "arguments": {"seconds": seconds}})

        if "fail" in available and ("fail" in lower or "error" in lower or "boom" in lower):
            calls.append({"name": "fail", "arguments": {"message": "intentional tool failure"}})

        if "echo" in available and not calls:
            calls.append({"name": "echo", "arguments": {"text": prompt[:200]}})

        if "json_dump" in available and "json" in lower:
            calls.append(
                {
                    "name": "json_dump",
                    "arguments": {"payload": json.dumps({"prompt": prompt[:80]})},
                }
            )

        return calls[:1]  # one tool per step keeps the loop simple
