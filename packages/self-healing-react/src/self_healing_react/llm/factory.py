"""Resolve the configured LLM provider."""

from __future__ import annotations

from self_healing_react.config import Settings, get_settings
from self_healing_react.llm.base import LLMProvider
from self_healing_react.llm.bedrock import BedrockLLMProvider
from self_healing_react.llm.mock import MockLLMProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "bedrock":
        return BedrockLLMProvider(
            region=settings.bedrock_region,
            model_id=settings.bedrock_model_id,
        )
    return MockLLMProvider()
