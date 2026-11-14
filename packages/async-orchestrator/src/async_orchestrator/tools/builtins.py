"""Built-in async tools used by demos and concurrency tests."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from async_orchestrator.tools.base import Tool


class EchoTool(Tool):
    name = "echo"
    description = "Echo text back to the agent (async no-op I/O stand-in)."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def run(self, **kwargs: Any) -> Any:
        text = str(kwargs.get("text", ""))
        await asyncio.sleep(0)  # yield to the event loop
        return {"echo": text}


class SleepTool(Tool):
    name = "sleep"
    description = "Non-blocking sleep for N seconds (demonstrates await vs busy-wait)."
    parameters = {
        "type": "object",
        "properties": {
            "seconds": {"type": "number", "minimum": 0, "maximum": 5},
        },
        "required": ["seconds"],
    }

    async def run(self, **kwargs: Any) -> Any:
        seconds = float(kwargs.get("seconds", 0.01))
        seconds = max(0.0, min(seconds, 5.0))
        await asyncio.sleep(seconds)
        return {"slept": seconds}


class FailTool(Tool):
    name = "fail"
    description = "Always raises — used to prove tool failures do not crash the loop."
    parameters = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": [],
    }

    async def run(self, **kwargs: Any) -> Any:
        await asyncio.sleep(0)
        raise RuntimeError(str(kwargs.get("message") or "tool intentionally failed"))


class JsonDumpTool(Tool):
    name = "json_dump"
    description = "Parse and pretty-print a JSON string."
    parameters = {
        "type": "object",
        "properties": {"payload": {"type": "string"}},
        "required": ["payload"],
    }

    async def run(self, **kwargs: Any) -> Any:
        await asyncio.sleep(0)
        raw = kwargs.get("payload", "{}")
        data = json.loads(raw) if isinstance(raw, str) else raw
        keys = list(data.keys()) if isinstance(data, dict) else []
        return {"pretty": json.dumps(data, indent=2), "keys": keys}


class BlockingAntiPatternTool(Tool):
    """
    Intentionally blocks the event loop with time.sleep.

    Used only in tests that prove why blocking work destroys concurrency.
    Never register this in production tool sets.
    """

    name = "blocking_sleep"
    description = "BLOCKS the event loop — anti-pattern demo only."
    parameters = {
        "type": "object",
        "properties": {"seconds": {"type": "number"}},
        "required": ["seconds"],
    }

    async def run(self, **kwargs: Any) -> Any:
        import time

        seconds = float(kwargs.get("seconds", 0.05))
        time.sleep(seconds)  # noqa: ASYNC251 — deliberate anti-pattern for demos
        return {"blocked": seconds}
