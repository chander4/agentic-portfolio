"""Strict tool router: propose → validate → retry with error trace → execute."""

from __future__ import annotations

import inspect
import time
from typing import Any

from pydantic import ValidationError

from strict_tool_router.config import Settings, get_settings
from strict_tool_router.llm.base import LLMProvider, Message, ToolSchema
from strict_tool_router.llm.factory import create_llm_provider
from strict_tool_router.models import RouteRequest, RouteResult, RouteStatus, ValidationAttempt
from strict_tool_router.registry import ToolDefinition, ToolRegistry

_SYSTEM_PROMPT = """You are a tool-argument generator.
Given a user request and a JSON Schema for ONE tool, output ONLY arguments for that tool.
Do not invent extra fields. Obey types, enums, and required fields exactly.
If you receive a VALIDATION_ERROR message, fix every listed issue and try again.
"""


class StrictToolRouter:
    """
    Schema-first tool execution engine.

    Stochastic model output is forced through a Pydantic gate. Invalid payloads
    never reach the handler; instead the validation error trace is appended to
    the conversation and the model is asked to correct itself (bounded retries).
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        llm: LLMProvider | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or create_llm_provider(self.settings)
        self.registry = registry or ToolRegistry()

    async def route(self, request: RouteRequest) -> RouteResult:
        started = time.perf_counter()
        max_retries = (
            request.max_retries
            if request.max_retries is not None
            else self.settings.max_retries
        )

        try:
            tool = self.registry.require(request.tool)
        except KeyError as exc:
            return RouteResult(
                tool=request.tool,
                status=RouteStatus.FAILED,
                prompt=request.prompt,
                error=str(exc),
                provider=self.llm.name,
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        schema = ToolSchema(
            name=tool.name,
            description=tool.description,
            parameters=tool.json_schema(),
        )
        messages: list[Message] = [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(
                role="user",
                content=(
                    f"Tool: {tool.name}\n"
                    f"Description: {tool.description}\n"
                    f"JSON Schema:\n{tool.json_schema()}\n\n"
                    f"User request:\n{request.prompt}"
                ),
            ),
        ]

        attempts: list[ValidationAttempt] = []
        last_error: str | None = None

        # attempt 0 + up to max_retries corrections
        for attempt_idx in range(max_retries + 1):
            proposal = await self.llm.propose_tool_args(
                messages,
                tool=schema,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )
            arguments = proposal.arguments if isinstance(proposal.arguments, dict) else {}

            try:
                validated = tool.validate(arguments)
            except ValidationError as exc:
                error_trace = tool.format_validation_error(exc)
                attempts.append(
                    ValidationAttempt(
                        attempt=attempt_idx,
                        arguments=arguments,
                        valid=False,
                        error_trace=error_trace,
                    )
                )
                last_error = error_trace
                messages.append(
                    Message(
                        role="assistant",
                        content=f"Proposed arguments: {arguments}",
                    )
                )
                messages.append(Message(role="user", content=error_trace))
                continue

            attempts.append(
                ValidationAttempt(
                    attempt=attempt_idx,
                    arguments=validated.model_dump(mode="json"),
                    valid=True,
                )
            )
            tool_result = await self._execute(tool, validated)
            return RouteResult(
                tool=tool.name,
                status=RouteStatus.SUCCEEDED,
                prompt=request.prompt,
                arguments=validated.model_dump(mode="json"),
                tool_result=tool_result,
                attempts=attempts,
                retries_used=attempt_idx,
                provider=self.llm.name,
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        return RouteResult(
            tool=tool.name,
            status=RouteStatus.REJECTED,
            prompt=request.prompt,
            attempts=attempts,
            retries_used=max_retries,
            error=last_error or "arguments rejected after retries",
            provider=self.llm.name,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    async def _execute(self, tool: ToolDefinition, args: Any) -> Any:
        result = tool.handler(args)
        if inspect.isawaitable(result):
            return await result
        return result
