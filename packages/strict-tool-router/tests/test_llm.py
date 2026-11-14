"""LLM provider factory and mock modes."""

from __future__ import annotations

import pytest
from strict_tool_router.config import Settings
from strict_tool_router.llm.base import Message, ToolSchema
from strict_tool_router.llm.bedrock import BedrockLLMProvider
from strict_tool_router.llm.factory import create_llm_provider
from strict_tool_router.llm.mock import MockLLMProvider
from strict_tool_router.schemas import ScheduleMeetingArgs


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
async def test_mock_bad_then_good_changes_after_validation_error() -> None:
    llm = MockLLMProvider(mode="bad_then_good", latency_ms=0.0)
    schema = ToolSchema(
        name="schedule_meeting",
        description="schedule",
        parameters=ScheduleMeetingArgs.model_json_schema(),
    )

    first = await llm.propose_tool_args(
        [Message(role="user", content="mode=bad_then_good")],
        tool=schema,
    )
    assert first.arguments.get("attendees") == "not-a-list" or first.arguments.get("title") == ""

    second = await llm.propose_tool_args(
        [
            Message(role="user", content="mode=bad_then_good"),
            Message(role="user", content="VALIDATION_ERROR for tool 'schedule_meeting'"),
        ],
        tool=schema,
    )
    # Corrected payload should validate
    ScheduleMeetingArgs.model_validate(second.arguments)
