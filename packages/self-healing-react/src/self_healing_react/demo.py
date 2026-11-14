"""CLI demo: broken tool call → stack trace → heal rewrite → success."""

from __future__ import annotations

import asyncio
import json

from self_healing_react.agent import SelfHealingReActAgent
from self_healing_react.config import Settings
from self_healing_react.llm.mock import MockLLMProvider
from self_healing_react.models import RunRequest


async def main() -> None:
    agent = SelfHealingReActAgent(
        settings=Settings(llm_provider="mock", max_heals=3),
        llm=MockLLMProvider(mode="fail_then_heal", latency_ms=1.0),
    )

    print("=== Self-Healing ReAct demo ===\n")
    print("Scenario: mock LLM first calls compile_python with a SyntaxError,")
    print("then rewrites after reading the HEAL_ERROR / stack trace.\n")

    result = await agent.run(
        RunRequest(
            goal="mode=fail_then_heal; Compile a Python snippet that sets result=42.",
            max_heals=3,
            max_steps=6,
        )
    )

    print(f"status:      {result.status.value}")
    print(f"heals_used:  {result.heals_used}")
    print(f"provider:    {result.provider}")
    print(f"answer:      {result.answer}")
    print("\nHeal log:")
    for heal in result.heals:
        mark = "HEALED" if heal.healed else "FAILED"
        print(f"  [{heal.attempt}] {mark} tool={heal.tool} args={heal.arguments}")
        first = heal.error_trace.splitlines()[0]
        print(f"       -> {first}")
        if heal.rewritten_arguments:
            print(f"       -> rewritten: {json.dumps(heal.rewritten_arguments)}")

    print("\nTrace:")
    for step in result.steps:
        print(f"  [{step.index}] {step.kind.value}: {step.content[:120]}")

    if result.status.value == "succeeded" and result.heals_used >= 1:
        print(
            "\nProof: first tool call raised; the agent parsed the stack trace, "
            "rewrote arguments, retried, and finished."
        )
    else:
        print("\nUnexpected result — check mock mode / max_heals.")


if __name__ == "__main__":
    asyncio.run(main())
