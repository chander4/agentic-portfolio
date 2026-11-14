"""CLI demo: invalid tool args → validation → retry → success."""

from __future__ import annotations

import asyncio
import json

from strict_tool_router.config import Settings
from strict_tool_router.llm.mock import MockLLMProvider
from strict_tool_router.models import RouteRequest
from strict_tool_router.router import StrictToolRouter


async def main() -> None:
    router = StrictToolRouter(
        settings=Settings(llm_provider="mock", max_retries=3),
        llm=MockLLMProvider(mode="bad_then_good", latency_ms=1.0),
    )

    print("=== Strict Pydantic Tool Router demo ===\n")
    print("Scenario: mock LLM first emits INVALID schedule_meeting args,")
    print("then corrects after receiving the VALIDATION_ERROR trace.\n")

    result = await router.route(
        RouteRequest(
            prompt="mode=bad_then_good; schedule a meeting title=Hiring sync",
            tool="schedule_meeting",
            max_retries=3,
        )
    )

    print(f"status:        {result.status.value}")
    print(f"retries_used:  {result.retries_used}")
    print(f"provider:      {result.provider}")
    print(f"final args:    {json.dumps(result.arguments, indent=2)}")
    print(f"tool_result:   {json.dumps(result.tool_result, indent=2)}")
    print("\nAttempt log:")
    for attempt in result.attempts:
        mark = "OK" if attempt.valid else "REJECTED"
        print(f"  [{attempt.attempt}] {mark}: {attempt.arguments}")
        if attempt.error_trace:
            first_line = attempt.error_trace.splitlines()[0]
            print(f"       -> {first_line}")

    if result.status.value == "succeeded" and result.retries_used >= 1:
        print(
            "\nProof: first proposal failed Pydantic validation; "
            "retry with the error trace produced a valid payload and the tool ran."
        )
    else:
        print("\nUnexpected result — check mock mode / max_retries.")


if __name__ == "__main__":
    asyncio.run(main())
