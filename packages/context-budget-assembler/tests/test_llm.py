"""LLM provider factory for summarization path."""

from __future__ import annotations

import pytest
from context_budget_assembler.config import Settings
from context_budget_assembler.llm.bedrock import BedrockLLMProvider
from context_budget_assembler.llm.factory import create_llm_provider
from context_budget_assembler.llm.mock import MockLLMProvider
from context_budget_assembler.tokens import estimate_tokens


def test_factory_defaults_to_mock() -> None:
    provider = create_llm_provider(Settings(llm_provider="mock"))
    assert isinstance(provider, MockLLMProvider)
    assert provider.name == "mock"


def test_factory_bedrock() -> None:
    provider = create_llm_provider(Settings(llm_provider="bedrock", bedrock_region="us-west-2"))
    assert isinstance(provider, BedrockLLMProvider)
    assert provider.region == "us-west-2"


@pytest.mark.asyncio
async def test_mock_summarize_shrinks() -> None:
    llm = MockLLMProvider(latency_ms=0.0, chars_per_token=4.0)
    text = ("detail " * 100).strip()
    out = await llm.summarize(text, target_tokens=20)
    assert out.startswith("[summary]")
    assert estimate_tokens(out, chars_per_token=4.0) <= 20
