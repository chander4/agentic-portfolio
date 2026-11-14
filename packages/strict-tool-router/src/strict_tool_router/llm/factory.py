"""Resolve the configured LLM provider."""

from __future__ import annotations

from strict_tool_router.config import Settings, get_settings
from strict_tool_router.llm.base import LLMProvider
from strict_tool_router.llm.bedrock import BedrockLLMProvider
from strict_tool_router.llm.mock import MockLLMProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "bedrock":
        return BedrockLLMProvider(
            region=settings.bedrock_region,
            model_id=settings.bedrock_model_id,
        )
    return MockLLMProvider()
