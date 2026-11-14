"""Token estimator and truncation helpers."""

from __future__ import annotations

from context_budget_assembler.tokens import estimate_tokens, truncate_to_tokens


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens("") == 0


def test_estimate_tokens_rounding() -> None:
    # 10 chars / 4 = 2.5 → ceil 3
    assert estimate_tokens("abcdefghij", chars_per_token=4.0) == 3


def test_truncate_to_tokens_respects_budget() -> None:
    text = "word " * 100
    out = truncate_to_tokens(text, 10, chars_per_token=4.0)
    assert estimate_tokens(out, chars_per_token=4.0) <= 10
    assert out.endswith("…")
