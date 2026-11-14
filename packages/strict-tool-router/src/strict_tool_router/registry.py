"""Tool registry: Pydantic schema + handler bound to a name."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from strict_tool_router.schemas import (
    ScheduleMeetingArgs,
    SearchDocsArgs,
    TransferFundsArgs,
)

ArgsT = TypeVar("ArgsT", bound=BaseModel)
Handler = Callable[[BaseModel], Awaitable[Any] | Any]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Handler

    def json_schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()

    def validate(self, arguments: dict[str, Any]) -> BaseModel:
        return self.args_model.model_validate(arguments)

    def format_validation_error(self, exc: ValidationError) -> str:
        """Human-readable error trace fed back to the LLM on retry."""
        lines = [
            f"VALIDATION_ERROR for tool '{self.name}' "
            f"(schema={self.args_model.__name__}):"
        ]
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
            lines.append(f"  - {loc}: {err.get('msg')} [type={err.get('type')}]")
        lines.append("Return a corrected JSON object that satisfies the schema.")
        return "\n".join(lines)


class ToolRegistry:
    def __init__(self, tools: list[ToolDefinition] | None = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        for tool in tools or default_tools():
            self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def require(self, name: str) -> ToolDefinition:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        return tool

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())


async def _schedule_meeting(args: ScheduleMeetingArgs) -> dict[str, Any]:
    return {
        "scheduled": True,
        "title": args.title,
        "attendees": args.attendees,
        "duration_minutes": args.duration_minutes,
        "priority": args.priority.value,
    }


async def _transfer_funds(args: TransferFundsArgs) -> dict[str, Any]:
    return {
        "transferred": True,
        "from_account": args.from_account,
        "to_account": args.to_account,
        "amount": args.amount,
        "currency": args.currency,
    }


async def _search_docs(args: SearchDocsArgs) -> dict[str, Any]:
    return {
        "hits": [
            {"title": f"Doc about {args.query}", "score": 0.91},
        ][: args.limit],
        "query": args.query,
        "tags": args.tags,
    }


def default_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="schedule_meeting",
            description="Schedule a meeting with email attendees and a bounded duration.",
            args_model=ScheduleMeetingArgs,
            handler=_schedule_meeting,  # type: ignore[arg-type]
        ),
        ToolDefinition(
            name="transfer_funds",
            description="Transfer a positive amount between two distinct accounts.",
            args_model=TransferFundsArgs,
            handler=_transfer_funds,  # type: ignore[arg-type]
        ),
        ToolDefinition(
            name="search_docs",
            description="Search internal docs with a non-empty query and optional tags.",
            args_model=SearchDocsArgs,
            handler=_search_docs,  # type: ignore[arg-type]
        ),
    ]
