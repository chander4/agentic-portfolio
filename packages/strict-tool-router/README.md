# #3 — Strict Pydantic Tool Router

**Status:** implemented  
**Stack:** FastAPI · Pydantic v2 · provider-agnostic LLM (AWS Bedrock / mock default)

## Problem

LLM tool/function calling is stochastic. Models invent fields, use the wrong types,
omit required keys, and occasionally return almost-JSON. If those payloads hit a
handler unchecked, you get runtime exceptions, partial side effects, or silent
corruption. Prompting harder is not a control plane.

Hiring managers evaluating agent engineers should see whether a candidate treats
**schema validation as a hard gate** — and whether the system can recover by
feeding the validation error back to the model instead of crashing.

## Design

```
HTTP (FastAPI) / library API
        │
        ▼
StrictToolRouter
    ├─ ToolRegistry          # name → Pydantic args model + handler
    ├─ LLMProvider           # Bedrock Converse | Mock (default)
    │       proposes JSON args for ONE tool
    ├─ Pydantic validate     # hard gate (JSON Schema from model_json_schema)
    │       │
    │       ├─ ok  → execute handler
    │       └─ err → append VALIDATION_ERROR trace → retry (bounded)
    └─ RouteResult           # attempts, retries_used, final args / rejection
```

Key properties:

| Concern | Approach |
|---|---|
| Schema-first | Each tool declares a Pydantic model; JSON Schema is derived, not hand-written |
| Hard gate | Invalid args never reach the handler |
| Automatic retry | Validation error trace is appended as a user message; model must correct |
| Bounded loops | `max_retries` caps correction attempts → `rejected` if still invalid |
| LLM portability | `LLMProvider` ABC; Bedrock Converse via `aioboto3`; mock for CI/demos |
| Proof | Demo + tests: bad args rejected; bad→good retry succeeds |

Grammar-constrained / schema-first narrative: the model may be stochastic, but
**actions are deterministic** once arguments pass the Pydantic model. Bedrock's
`toolSpec` / `toolChoice` is a soft constraint; Pydantic is the final authority.

## Why this matters for hiring

Chase builds **production agentic workflows on AWS Bedrock** from a senior DevOps
background. This package shows the control plane around tool use: typed contracts,
fail-closed validation, and retry-with-trace — the difference between a demo chat
bot and something you would put in front of money movement or calendar mutations.

## Quick start

From the monorepo root (requires [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --all-packages
export LLM_PROVIDER=mock   # Windows: $env:LLM_PROVIDER="mock"

# Library / CLI demo (bad → VALIDATION_ERROR → corrected → success)
uv run python -m strict_tool_router.demo

# API
uv run uvicorn strict_tool_router.main:app --app-dir packages/strict-tool-router/src --port 8081

# Tests
uv run pytest packages/strict-tool-router/tests -q
```

### Demo: retry after validation failure

```bash
curl -X POST http://127.0.0.1:8081/demo/retry \
  -H "content-type: application/json" \
  -d "{\"scenario\":\"bad_then_good\",\"tool\":\"schedule_meeting\"}"
```

Expect `status=succeeded`, `retries_used=1`, and an `attempts` log showing the
first rejection plus the corrected payload.

### Bedrock mode

```bash
export LLM_PROVIDER=bedrock
export AWS_REGION=us-east-1
# plus standard AWS credentials / IAM role
uv run uvicorn strict_tool_router.main:app --app-dir packages/strict-tool-router/src --port 8081
```

No credentials? Stay on `LLM_PROVIDER=mock` — CI and local demos are designed for that.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `GET` | `/tools` | Registered tools + JSON Schema |
| `POST` | `/route` | Propose → validate → retry → execute |
| `POST` | `/demo/retry` | Deterministic bad-then-good hiring demo |

### Library usage

```python
from strict_tool_router import StrictToolRouter
from strict_tool_router.models import RouteRequest

router = StrictToolRouter()  # mock by default
result = await router.route(
    RouteRequest(prompt="mode=always_good; title=Sync", tool="schedule_meeting")
)
assert result.status.value == "succeeded"
```

## What this proves

1. **Validation rejects bad args** — wrong types, empty required fields, bad enums.
2. **Retry succeeds with a corrected payload** — error trace is actionable input.
3. **Handlers stay pure** — only Pydantic-validated models are executed.
4. **Provider-agnostic core** — Bedrock for production shape, mock for deterministic demos.

## Layout

```
src/strict_tool_router/
  main.py         # FastAPI app
  router.py       # propose → validate → retry loop
  registry.py     # tool definitions + handlers
  schemas.py      # Pydantic argument models
  demo.py         # CLI proof
  config.py
  models.py
  llm/            # Bedrock + mock providers
tests/            # validation, retry, API, LLM factory
```
