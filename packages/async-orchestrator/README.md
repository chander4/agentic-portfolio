# #1 — Async Agent Orchestrator

**Status:** implemented  
**Stack:** FastAPI · asyncio · provider-agnostic LLM (AWS Bedrock default / mock for demos)

## Problem

Most agent demos hide a serial loop:

```python
while True:
    response = llm.call(messages)   # blocks the thread
    result = tool.run(...)          # blocks again
```

That pattern cannot run 100 agents at once. One slow tool call stalls every peer. One uncaught tool exception can take down the process. Hiring managers evaluating “agent engineers” should see whether a candidate understands **event-loop concurrency**, not just prompt chaining.

## Design

```
HTTP (FastAPI)
    │
    ▼
AgentOrchestrator
    ├─ Semaphore(max_concurrent)     # backpressure
    ├─ asyncio.Task per agent        # isolation
    ├─ LLMProvider (Bedrock | Mock)  # awaitable inference
    └─ ToolRegistry                  # timeout + error capture
```

Key properties:

| Concern | Approach |
|---|---|
| Concurrency | Each agent is an `asyncio.Task`; I/O is awaited, not spun |
| Backpressure | `asyncio.Semaphore` caps in-flight agents |
| Tool failures | Caught at the registry boundary → `ToolCallResult(ok=False)` |
| Agent failures | Guarded runner; siblings keep running |
| LLM portability | `LLMProvider` ABC; Bedrock Converse via `aioboto3`; mock for CI |
| Proof | `/demo/concurrency` + tests assert wall time ≪ serial time |

## Why this matters for hiring

Chase builds **production agentic workflows on AWS Bedrock** from a senior DevOps background. This package is the concurrency foundation those systems need: non-blocking tool calls, graceful degradation, and a clear story for why blocking SDK usage is a production incident waiting to happen.

## Quick start

From the monorepo root (requires [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --all-packages
export LLM_PROVIDER=mock   # Windows: $env:LLM_PROVIDER="mock"

# Run the API
uv run uvicorn async_orchestrator.main:app --app-dir packages/async-orchestrator/src --port 8080

# Blocking vs async side-by-side demo
uv run python -m async_orchestrator.demo_blocking

# Tests (includes 100-agent concurrency proof)
uv run pytest packages/async-orchestrator/tests -q
```

### Demo: 100 concurrent agents

```bash
curl -X POST "http://127.0.0.1:8080/demo/concurrency?count=100&sleep_seconds=0.05"
```

Expect wall time near `0.05s` (+ overhead), **not** `5.0s`. The response includes `speedup_vs_serial`.

### Bedrock mode

```bash
export LLM_PROVIDER=bedrock
export AWS_REGION=us-east-1
# plus standard AWS credentials / IAM role
uv run uvicorn async_orchestrator.main:app --app-dir packages/async-orchestrator/src --port 8080
```

No credentials? Stay on `LLM_PROVIDER=mock` — CI and local demos are designed for that.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `GET` | `/stats` | Active / completed / failed counts |
| `POST` | `/tasks` | Submit one agent task (202) |
| `POST` | `/tasks/batch` | Submit up to 500 tasks |
| `GET` | `/tasks/{id}` | Full task record + steps |
| `POST` | `/tasks/{id}/wait` | Block until terminal state |
| `POST` | `/demo/concurrency` | Built-in concurrency proof |

## What this proves

1. **Event-driven > busy loops** — measured, not claimed (`demo_blocking`, concurrency tests).
2. **Failure isolation** — intentional `fail` tools and LLM exceptions do not crash the loop.
3. **Provider-agnostic core** — Bedrock for production shape, mock for deterministic demos.
4. **Production posture** — timeouts, semaphores, typed models, CI-ready package layout.

## Layout

```
src/async_orchestrator/
  main.py            # FastAPI app
  orchestrator.py    # concurrent agent runtime
  demo_blocking.py   # blocking vs async demonstration
  config.py
  models.py
  llm/               # Bedrock + mock providers
  tools/             # async tool registry + builtins
tests/               # concurrency, recovery, API, LLM
```
