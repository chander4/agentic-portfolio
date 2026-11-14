"""CLI demo: pack overflowing context under a hard token budget."""

from __future__ import annotations

import asyncio
import json

from context_budget_assembler.assembler import ContextBudgetAssembler
from context_budget_assembler.config import Settings
from context_budget_assembler.demo_scenarios import build_scenario
from context_budget_assembler.llm.mock import MockLLMProvider


async def main() -> None:
    assembler = ContextBudgetAssembler(
        settings=Settings(llm_provider="mock", chars_per_token=4.0),
        llm=MockLLMProvider(latency_ms=1.0, chars_per_token=4.0),
    )

    print("=== Context Budget Assembler demo ===\n")
    print("Scenario: overflow_drop_low_priority (budget=80 tokens)\n")

    result = await assembler.assemble(
        build_scenario("overflow_drop_low_priority", budget_tokens=80)
    )

    print(f"budget:     {result.budget_tokens}")
    print(f"used:       {result.used_tokens}")
    print(f"leftover:   {result.leftover_tokens}")
    print(f"dropped:    {result.dropped_ids}")
    print("\nDecisions:")
    for item in result.packed:
        print(
            f"  [{item.decision.value}] {item.id} "
            f"pri={item.priority} tokens={item.packed_tokens}/{item.original_tokens}"
        )
    print("\nPrompt preview:")
    print(result.prompt_text[:500])
    print("\nJSON summary:")
    print(
        json.dumps(
            {
                "used_tokens": result.used_tokens,
                "dropped_ids": result.dropped_ids,
                "decisions": [p.decision.value for p in result.packed],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
