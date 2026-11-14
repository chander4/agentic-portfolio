"""AWS Bedrock Converse provider that asks for JSON tool arguments."""

from __future__ import annotations

import json
from typing import Any

from strict_tool_router.llm.base import LLMProvider, Message, ToolProposal, ToolSchema


class BedrockLLMProvider(LLMProvider):
    """
    Production path: Bedrock Converse with a toolSpec derived from the Pydantic schema.

    The router still validates the returned ``input`` with Pydantic — Bedrock's
    tool schema is a soft constraint; Pydantic is the hard gate.
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

    async def propose_tool_args(
        self,
        messages: list[Message],
        *,
        tool: ToolSchema,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> ToolProposal:
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
            "toolConfig": {
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": {
                                "json": tool.parameters or {"type": "object"},
                            },
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": tool.name}},
            },
        }
        if system:
            kwargs["system"] = [{"text": "\n\n".join(system)}]

        session = aioboto3.Session()
        async with session.client("bedrock-runtime", region_name=self.region) as client:
            response = await client.converse(**kwargs)

        return self._parse_response(response, fallback_name=tool.name)

    def _to_converse_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role in {"user", "assistant"}:
                out.append({"role": msg.role, "content": [{"text": msg.content}]})
        return out or [{"role": "user", "content": [{"text": "Propose tool arguments."}]}]

    def _parse_response(self, response: dict[str, Any], *, fallback_name: str) -> ToolProposal:
        content_blocks = response.get("output", {}).get("message", {}).get("content", [])
        texts: list[str] = []
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
                if not isinstance(args, dict):
                    args = {"raw": args}
                return ToolProposal(
                    name=use.get("name") or fallback_name,
                    arguments=args,
                    raw_text=json.dumps(args),
                )

        # No toolUse block — try to parse JSON from text
        blob = "\n".join(texts).strip()
        try:
            parsed = json.loads(blob)
            if isinstance(parsed, dict):
                return ToolProposal(name=fallback_name, arguments=parsed, raw_text=blob)
        except json.JSONDecodeError:
            pass
        return ToolProposal(name=fallback_name, arguments={"raw": blob}, raw_text=blob)
