"""Deterministic mock summarizer for demos/CI."""

from __future__ import annotations

import asyncio

from context_budget_assembler.llm.base import LLMProvider
from context_budget_assembler.tokens import truncate_to_tokens


class MockLLMProvider(LLMProvider):
    """
    Summarize by hard truncation with a marker — proves the assembler can call
    an LLM path without AWS credentials.
    """

    name = "mock"

    def __init__(self, *, latency_ms: float = 5.0, chars_per_token: float = 4.0) -> None:
        self.latency_ms = latency_ms
        self.chars_per_token = chars_per_token

    async def summarize(
        self,
        text: str,
        *,
        target_tokens: int,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        await asyncio.sleep(self.latency_ms / 1000.0)
        # Leave room for the summary prefix inside the target budget.
        prefix = "[summary] "
        prefix_tokens = max(1, len(prefix) // 4)
        body_budget = max(1, target_tokens - prefix_tokens)
        body = truncate_to_tokens(
            text, body_budget, chars_per_token=self.chars_per_token
        )
        return f"{prefix}{body}"
