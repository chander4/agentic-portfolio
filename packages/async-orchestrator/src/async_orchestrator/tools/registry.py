"""Tool registry with concurrent, timeout-bounded invocation."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from async_orchestrator.models import ToolCallResult
from async_orchestrator.tools.base import Tool
from async_orchestrator.tools.builtins import EchoTool, FailTool, JsonDumpTool, SleepTool


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or default_tools():
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_specs(self, names: list[str] | None = None) -> list[Tool]:
        if names is None:
            return list(self._tools.values())
        return [self._tools[n] for n in names if n in self._tools]

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout: float = 15.0,
    ) -> ToolCallResult:
        """
        Invoke a tool without letting failures or hangs take down the orchestrator.

        - Missing tool → failed ToolCallResult (not an exception)
        - Tool exception → captured in ToolCallResult.error
        - Timeout → failed ToolCallResult
        """
        started = time.perf_counter()
        tool = self.get(name)
        if tool is None:
            return ToolCallResult(
                name=name,
                ok=False,
                error=f"unknown tool: {name}",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        try:
            result = await asyncio.wait_for(tool.run(**(arguments or {})), timeout=timeout)
            return ToolCallResult(
                name=name,
                ok=True,
                result=result,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
        except TimeoutError:
            return ToolCallResult(
                name=name,
                ok=False,
                error=f"tool timed out after {timeout}s",
                duration_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:  # noqa: BLE001 — intentional isolation boundary
            return ToolCallResult(
                name=name,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - started) * 1000,
            )


def default_tools() -> list[Tool]:
    return [EchoTool(), SleepTool(), FailTool(), JsonDumpTool()]
