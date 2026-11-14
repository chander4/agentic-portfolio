"""Provider-agnostic LLM interface for optional segment summarization."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class Message:
    role: str
    content: str


class LLMProvider(ABC):
    """Swap Bedrock / mock without touching the assembler."""

    name: str

    @abstractmethod
    async def summarize(
        self,
        text: str,
        *,
        target_tokens: int,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        """Return a shorter version of ``text`` aiming for ``target_tokens``."""

        raise NotImplementedError
