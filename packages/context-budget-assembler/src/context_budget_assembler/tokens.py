"""Deterministic token estimation (no tiktoken dependency)."""

from __future__ import annotations

import math


def estimate_tokens(text: str, *, chars_per_token: float = 4.0) -> int:
    """
    Cheap, stable estimator for demos and CI.

    Real deployments can swap this for a model tokenizer; the assembler only
    needs a monotonic estimate so packing decisions stay testable.
    """
    if not text:
        return 0
    if chars_per_token <= 0:
        raise ValueError("chars_per_token must be positive")
    return max(1, math.ceil(len(text) / chars_per_token))


def truncate_to_tokens(text: str, max_tokens: int, *, chars_per_token: float = 4.0) -> str:
    """Trim text so estimate_tokens(result) <= max_tokens. Keeps a trailing ellipsis when cut."""
    if max_tokens <= 0:
        return ""
    if estimate_tokens(text, chars_per_token=chars_per_token) <= max_tokens:
        return text

    # Reserve ~1 token for the ellipsis marker when possible
    budget = max_tokens - 1 if max_tokens > 1 else max_tokens
    max_chars = max(0, int(budget * chars_per_token))
    cut = text[:max_chars].rstrip()
    if max_tokens > 1:
        return f"{cut}…"
    return cut[: max(0, int(max_tokens * chars_per_token))]
