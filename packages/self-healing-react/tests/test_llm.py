"""LLM provider factory and mock heal modes."""

from __future__ import annotations

import pytest
from self_healing_react.config import Settings
from self_healing_react.llm.base import Message, ToolSchema
from self_healing_react.llm.bedrock import BedrockLLMProvider
from self_healing_react.llm.factory import create_llm_provider
from self_healing_react.llm.mock import MockLLMProvider


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
async def test_mock_fail_then_heal_rewrites_after_heal_error() -> None:
    llm = MockLLMProvider(mode="fail_then_heal", latency_ms=0.0)
    tools = [
        ToolSchema(
            name="compile_python",
            description="compile",
            parameters={"type": "object", "properties": {"source": {"type": "string"}}},
        )
    ]

    first = await llm.propose_action(
        [Message(role="user", content="mode=fail_then_heal; compile")],
        tools=tools,
    )
    assert first.tool == "compile_python"
    assert 'result = "hello' in first.arguments.get("source", "")

    second = await llm.propose_action(
        [
            Message(role="user", content="mode=fail_then_heal; compile"),
            Message(
                role="user",
                content="HEAL_ERROR for tool 'compile_python':\n  exception: SyntaxError",
            ),
        ],
        tools=tools,
    )
    assert second.tool == "compile_python"
    assert second.arguments.get("source") == "result = 42"
