"""AWS Bedrock Converse provider for ReAct action proposals."""

from __future__ import annotations

import json
import re
from typing import Any

from self_healing_react.llm.base import AgentAction, LLMProvider, Message, ToolSchema


class BedrockLLMProvider(LLMProvider):
    """
    Production path: Bedrock Converse with toolSpecs for available tools.

    The agent still executes tools locally and runs the heal loop on failures —
    Bedrock only proposes the next thought/action.
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

    async def propose_action(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSchema],
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> AgentAction:
        import aioboto3

        system = [m.content for m in messages if m.role == "system"]
        converse_messages = self._to_converse_messages(
            [m for m in messages if m.role != "system"]
        )

        tool_config = {
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
            + [
                {
                    "toolSpec": {
                        "name": "final_answer",
                        "description": "Return the final answer to the user when done.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {"answer": {"type": "string"}},
                                "required": ["answer"],
                            }
                        },
                    }
                }
            ]
        }

        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": converse_messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
            "toolConfig": tool_config,
        }
        if system:
            kwargs["system"] = [{"text": "\n\n".join(system)}]

        session = aioboto3.Session()
        async with session.client("bedrock-runtime", region_name=self.region) as client:
            response = await client.converse(**kwargs)

        return self._parse_response(response)

    def _to_converse_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role in {"user", "assistant"}:
                out.append({"role": msg.role, "content": [{"text": msg.content}]})
        return out or [{"role": "user", "content": [{"text": "Begin."}]}]

    def _parse_response(self, response: dict[str, Any]) -> AgentAction:
        content_blocks = response.get("output", {}).get("message", {}).get("content", [])
        texts: list[str] = []
        for block in content_blocks:
            if "text" in block:
                texts.append(block["text"])
            if "toolUse" in block:
                use = block["toolUse"]
                name = use.get("name") or ""
                args = use.get("input", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                if not isinstance(args, dict):
                    args = {"raw": args}
                thought = "\n".join(texts).strip() or f"Calling {name}"
                if name == "final_answer":
                    return AgentAction(
                        thought=thought,
                        final_answer=str(args.get("answer", "")),
                        raw_text=json.dumps(args),
                    )
                return AgentAction(
                    thought=thought,
                    tool=name,
                    arguments=args,
                    raw_text=json.dumps(args),
                )

        blob = "\n".join(texts).strip()
        return _parse_json_action(blob)


def _parse_json_action(blob: str) -> AgentAction:
    try:
        parsed = json.loads(blob)
        if isinstance(parsed, dict):
            if parsed.get("final_answer"):
                return AgentAction(
                    thought=str(parsed.get("thought", "")),
                    final_answer=str(parsed["final_answer"]),
                    raw_text=blob,
                )
            return AgentAction(
                thought=str(parsed.get("thought", "")),
                tool=parsed.get("tool"),
                arguments=parsed.get("arguments") or {},
                raw_text=blob,
            )
    except json.JSONDecodeError:
        pass
    # Last resort: treat free text as a final answer
    match = re.search(r"FINAL:\s*(.+)", blob, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return AgentAction(thought="final", final_answer=match.group(1).strip(), raw_text=blob)
    return AgentAction(thought=blob, final_answer=blob or "No action proposed", raw_text=blob)
