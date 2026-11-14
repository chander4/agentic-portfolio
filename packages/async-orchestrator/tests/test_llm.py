"""LLM provider factory and mock behavior."""

from __future__ import annotations

import pytest
from async_orchestrator.config import Settings
from async_orchestrator.llm.base import Message
from async_orchestrator.llm.bedrock import BedrockLLMProvider
from async_orchestrator.llm.factory import create_llm_provider
from async_orchestrator.llm.mock import MockLLMProvider


def test_factory_defaults_to_mock() -> None:
    provider = create_llm_provider(Settings(llm_provider="mock"))
    assert isinstance(provider, MockLLMProvider)
    assert provider.name == "mock"


def test_factory_bedrock() -> None:
    provider = create_llm_provider(Settings(llm_provider="bedrock", bedrock_region="us-west-2"))
    assert isinstance(provider, BedrockLLMProvider)
    assert provider.region == "us-west-2"
    assert provider.name == "bedrock"


@pytest.mark.asyncio
async def test_mock_emits_sleep_tool_then_final() -> None:
    llm = MockLLMProvider(latency_ms=1.0)
    from async_orchestrator.llm.base import ToolSpec

    tools = [ToolSpec(name="sleep", description="sleep", parameters={})]
    first = await llm.complete(
        [Message(role="user", content="please sleep 0.01")],
        tools=tools,
    )
    assert first.tool_calls
    assert first.tool_calls[0]["name"] == "sleep"

    second = await llm.complete(
        [
            Message(role="user", content="please sleep 0.01"),
            Message(role="tool", content="sleep: {\"slept\": 0.01}"),
        ],
        tools=tools,
    )
    assert not second.tool_calls
    assert "Completed" in second.content
