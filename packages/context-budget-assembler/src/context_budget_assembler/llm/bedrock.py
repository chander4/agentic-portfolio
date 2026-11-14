"""AWS Bedrock Converse provider for summarization."""

from __future__ import annotations

from typing import Any

from context_budget_assembler.llm.base import LLMProvider


class BedrockLLMProvider(LLMProvider):
    """Production path: ask Bedrock to compress a segment to a token target."""

    name = "bedrock"

    def __init__(
        self,
        *,
        region: str = "us-east-1",
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
    ) -> None:
        self.region = region
        self.model_id = model_id

    async def summarize(
        self,
        text: str,
        *,
        target_tokens: int,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        import aioboto3

        prompt = (
            f"Summarize the following text to fit roughly {target_tokens} tokens. "
            "Preserve key facts. Return only the summary.\n\n"
            f"{text}"
        )
        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {
                "maxTokens": min(max_tokens, max(64, target_tokens * 2)),
                "temperature": temperature,
            },
        }

        session = aioboto3.Session()
        async with session.client("bedrock-runtime", region_name=self.region) as client:
            response = await client.converse(**kwargs)

        blocks = response.get("output", {}).get("message", {}).get("content", [])
        parts = [b["text"] for b in blocks if "text" in b]
        return "\n".join(parts).strip() or text
