"""AWS Bedrock Converse API provider (async via aioboto3)."""

from __future__ import annotations

import json
from typing import Any

from async_orchestrator.llm.base import LLMProvider, LLMResponse, Message, ToolSpec


class BedrockLLMProvider(LLMProvider):
    """
    Production default for Chase's stack: AWS Bedrock Converse.

    Uses aioboto3 so inference never blocks the event loop. Credentials come from
    the standard AWS chain (env, shared config, IAM role) — never hard-coded.
    """

    name = "bedrock"

    def __init__(
        self,
        *,
        region: str = "us-east-1",
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
    ) -> None:
        self.region = region
        self.model_id = model_id

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        import aioboto3

        system = [m.content for m in messages if m.role == "system"]
        converse_messages = self._to_converse_messages(
            [m for m in messages if m.role != "system"]
        )

        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": converse_messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            kwargs["system"] = [{"text": "\n\n".join(system)}]
        if tools:
            kwargs["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": {"json": t.parameters or {"type": "object"}},
                        }
                    }
                    for t in tools
                ]
            }

        session = aioboto3.Session()
        async with session.client("bedrock-runtime", region_name=self.region) as client:
            response = await client.converse(**kwargs)

        return self._parse_response(response)

    def _to_converse_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool":
                # Tool results are folded into a user message for Converse.
                out.append(
                    {
                        "role": "user",
                        "content": [{"text": f"[tool_result] {msg.content}"}],
                    }
                )
            elif msg.role in {"user", "assistant"}:
                out.append({"role": msg.role, "content": [{"text": msg.content}]})
        return out or [{"role": "user", "content": [{"text": ""}]}]

    def _parse_response(self, response: dict[str, Any]) -> LLMResponse:
        content_blocks = response.get("output", {}).get("message", {}).get("content", [])
        texts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            if "text" in block:
                texts.append(block["text"])
            if "toolUse" in block:
                use = block["toolUse"]
                args = use.get("input", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                tool_calls.append({"name": use.get("name", ""), "arguments": args})

        return LLMResponse(
            content="\n".join(texts).strip(),
            tool_calls=tool_calls,
            raw=response,
        )
