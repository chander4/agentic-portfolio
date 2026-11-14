"""Resolve the configured LLM provider."""

from __future__ import annotations

from async_orchestrator.config import Settings, get_settings
from async_orchestrator.llm.base import LLMProvider
from async_orchestrator.llm.bedrock import BedrockLLMProvider
from async_orchestrator.llm.mock import MockLLMProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "bedrock":
        return BedrockLLMProvider(
            region=settings.bedrock_region,
            model_id=settings.bedrock_model_id,
        )
    return MockLLMProvider()
