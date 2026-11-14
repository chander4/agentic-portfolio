"""Resolve the configured LLM provider."""

from __future__ import annotations

from context_budget_assembler.config import Settings, get_settings
from context_budget_assembler.llm.base import LLMProvider
from context_budget_assembler.llm.bedrock import BedrockLLMProvider
from context_budget_assembler.llm.mock import MockLLMProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "bedrock":
        return BedrockLLMProvider(
            region=settings.bedrock_region,
            model_id=settings.bedrock_model_id,
        )
    return MockLLMProvider(chars_per_token=settings.chars_per_token)
