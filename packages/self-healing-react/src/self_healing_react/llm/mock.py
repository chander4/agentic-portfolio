"""Deterministic mock LLM: fail once → heal, or exhaust heals."""

from __future__ import annotations

import asyncio
import json
import re

from self_healing_react.llm.base import AgentAction, LLMProvider, Message, ToolSchema


class MockLLMProvider(LLMProvider):
    """
    Controllable ReAct mock for hire-proof demos.

    Modes (constructor default or inferred from goal text):
    - ``fail_then_heal`` — first tool call is broken; after HEAL_ERROR, rewrite succeeds
    - ``always_fail`` — keeps emitting the same broken call (proves give-up)
    - ``always_ok`` — succeeds on the first tool call
    """

    name = "mock"

    def __init__(
        self,
        *,
        latency_ms: float = 5.0,
        mode: str = "fail_then_heal",
    ) -> None:
        self.latency_ms = latency_ms
        self.mode = mode
        self._calls = 0

    async def propose_action(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSchema],
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> AgentAction:
        await asyncio.sleep(self.latency_ms / 1000.0)
        self._calls += 1
        mode = self._resolve_mode(messages)
        tool_names = {t.name for t in tools}
        preferred = self._preferred_tool(messages, tool_names)

        # After a successful observation, emit a final answer
        if self._last_observation_ok(messages):
            value = self._extract_observation_value(messages)
            return AgentAction(
                thought="Tool succeeded; return the result.",
                final_answer=f"Done. Result={value}",
                raw_text=json.dumps({"final_answer": f"Done. Result={value}"}),
            )

        has_heal = any(m.role == "user" and "HEAL_ERROR" in m.content for m in messages)

        if mode == "always_ok" or (mode == "fail_then_heal" and has_heal):
            args = self._good_args(preferred, messages)
            thought = "Prior error fixed; retrying with corrected arguments."
        elif mode == "always_fail" or (mode == "fail_then_heal" and not has_heal):
            args = self._bad_args(preferred)
            thought = "Attempting the tool (intentionally broken on first try)."
        else:
            args = self._good_args(preferred, messages)
            thought = "Calling the tool."

        payload = {"thought": thought, "tool": preferred, "arguments": args}
        return AgentAction(
            thought=thought,
            tool=preferred,
            arguments=args,
            raw_text=json.dumps(payload),
        )

    def _resolve_mode(self, messages: list[Message]) -> str:
        blob = " ".join(m.content for m in messages if m.role == "user").lower()
        if "always_fail" in blob or "mode=always_fail" in blob:
            return "always_fail"
        if "always_ok" in blob or "mode=always_ok" in blob:
            return "always_ok"
        if "fail_then_heal" in blob or "mode=fail_then_heal" in blob:
            return "fail_then_heal"
        return self.mode

    def _preferred_tool(self, messages: list[Message], tool_names: set[str]) -> str:
        # Prefer the goal text only — tool schema dumps contain words like
        # "expression" / "path" and would otherwise steal routing.
        goal = next((m.content for m in messages if m.role == "user"), "")
        # Strip the "Available tools:" appendix if the agent concatenated schemas.
        goal = goal.split("Available tools:", 1)[0].lower()
        if "compile_python" in tool_names and (
            "compile" in goal or "python" in goal or "snippet" in goal
        ):
            return "compile_python"
        if "eval_math" in tool_names and (
            "math" in goal or "divide" in goal or "express" in goal or "multipl" in goal
        ):
            return "eval_math"
        if "lookup_path" in tool_names and (
            "lookup" in goal or "dotted" in goal or "payload" in goal
        ):
            return "lookup_path"
        if "compile_python" in tool_names:
            return "compile_python"
        return next(iter(tool_names))

    def _bad_args(self, tool: str) -> dict:
        if tool == "compile_python":
            # Unclosed string → SyntaxError from compile() with lineno/offset
            return {"source": 'result = "hello', "mode": "exec"}
        if tool == "eval_math":
            return {"expression": "1/0"}
        if tool == "lookup_path":
            return {"payload": {"user": {"id": 1}}, "path": "user.missing"}
        return {"broken": True}

    def _good_args(self, tool: str, messages: list[Message]) -> dict:
        if tool == "compile_python":
            # Prefer healing from HEAL_ERROR context when present
            return {"source": "result = 42", "mode": "exec"}
        if tool == "eval_math":
            expr = _extract(r"expression[=:]\s*([^\n;]+)", _blob(messages)) or "6*7"
            # If prior was divide-by-zero, heal to a safe expression
            if any("ZeroDivisionError" in m.content for m in messages):
                expr = "6*7"
            return {"expression": expr.strip()}
        if tool == "lookup_path":
            return {"payload": {"user": {"id": 1, "name": "chase"}}, "path": "user.name"}
        return {}

    def _last_observation_ok(self, messages: list[Message]) -> bool:
        for msg in reversed(messages):
            if msg.role == "user" and msg.content.startswith("OBSERVATION:"):
                return '"ok": true' in msg.content.lower() or "'ok': True" in msg.content
            if msg.role == "user" and "HEAL_ERROR" in msg.content:
                return False
        return False

    def _extract_observation_value(self, messages: list[Message]) -> str:
        for msg in reversed(messages):
            if msg.role == "user" and msg.content.startswith("OBSERVATION:"):
                match = re.search(r"['\"]value['\"]\s*:\s*([^,}]+)", msg.content)
                if match:
                    return match.group(1).strip().strip("'\"")
                return "ok"
        return "ok"


def _blob(messages: list[Message]) -> str:
    return " ".join(m.content for m in messages if m.role == "user")


def _extract(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1) if match else None
