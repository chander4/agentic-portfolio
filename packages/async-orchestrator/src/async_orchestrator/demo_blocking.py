"""
Side-by-side demo: blocking time.sleep vs await asyncio.sleep under concurrency.

Run::

    uv run python -m async_orchestrator.demo_blocking

This is the hiring-facing proof that a ``while True`` + blocking I/O agent loop
cannot scale, while an event-driven asyncio orchestrator can.
"""

from __future__ import annotations

import asyncio
import time


async def blocking_worker(seconds: float) -> None:
    # Simulates LLM/tool calls that block the thread (requests, boto3 sync, time.sleep).
    time.sleep(seconds)


async def async_worker(seconds: float) -> None:
    await asyncio.sleep(seconds)


async def run_batch(label: str, worker, n: int, seconds: float) -> float:
    started = time.perf_counter()
    await asyncio.gather(*(worker(seconds) for _ in range(n)))
    elapsed = time.perf_counter() - started
    print(f"{label:28} n={n:3} sleep={seconds:.3f}s  wall={elapsed:7.3f}s")
    return elapsed


async def main() -> None:
    n = 100
    seconds = 0.05
    print("=== Blocking vs event-driven concurrency ===")
    print(f"Running {n} workers that each 'work' for {seconds}s\n")

    blocked = await run_batch("blocking time.sleep", blocking_worker, n, seconds)
    concurrent = await run_batch("await asyncio.sleep", async_worker, n, seconds)

    print("\nInterpretation:")
    print(f"  Serial expectation : ~{n * seconds:.2f}s")
    print(f"  Blocking wall time : {blocked:.2f}s  (~ serial - event loop stuck)")
    print(f"  Async wall time    : {concurrent:.2f}s  (~ one sleep - loop interleaved)")
    print(f"  Speedup            : {blocked / concurrent:.1f}x")
    print(
        "\nAgent orchestrators that call sync SDKs inside the loop look like the "
        "blocking column. This package keeps LLM + tools awaitable so production "
        "looks like the async column."
    )


if __name__ == "__main__":
    asyncio.run(main())
