"""Async tool protocol — every tool must be awaitable (never block the loop)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        raise NotImplementedError
