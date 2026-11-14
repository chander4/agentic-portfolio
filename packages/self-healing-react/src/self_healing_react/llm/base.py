"""Provider-agnostic LLM interface for ReAct steps and heal rewrites."""

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
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentAction:
    """One ReAct action proposed by the model."""

    thought: str
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    final_answer: str | None = None
    raw_text: str = ""


class LLMProvider(ABC):
    """Swap Bedrock / mock without touching the agent loop."""

    name: str

    @abstractmethod
    async def propose_action(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSchema],
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> AgentAction:
        """Return the next thought/action or a final answer."""

        raise NotImplementedError
