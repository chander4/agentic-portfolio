"""Provider-agnostic LLM interface for schema-constrained tool arguments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Message:
    role: str
    content: str


@dataclass(slots=True)
class ToolSchema:
    """JSON Schema the model must satisfy when proposing tool arguments."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolProposal:
    """Raw model output before Pydantic validation."""

    name: str
    arguments: dict[str, Any]
    raw_text: str = ""


class LLMProvider(ABC):
    """Swap Bedrock / mock without touching the router."""

    name: str

    @abstractmethod
    async def propose_tool_args(
        self,
        messages: list[Message],
        *,
        tool: ToolSchema,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> ToolProposal:
        """Return a candidate tool call; router validates against the Pydantic model."""

        raise NotImplementedError
