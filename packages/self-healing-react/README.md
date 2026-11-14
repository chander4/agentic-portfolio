# #5 — Self-Healing ReAct

**Status:** implemented  
**Stack:** FastAPI · asyncio · provider-agnostic LLM (AWS Bedrock / mock default)

## Problem

Tool-using agents fail in production for boring reasons: bad arguments, syntax
errors from a compiler API, `KeyError` deep in a payload, divide-by-zero in a
generated expression. Most demos crash the loop and dump a traceback to logs.
Hiring managers evaluating agent engineers should see whether a candidate treats
**runtime failures as recoverable signals** — parse the stack trace, rewrite the
failing tool call, and retry under a hard budget.

## Design

```
HTTP (FastAPI) / library API
        │
        ▼
SelfHealingReActAgent
    ├─ ToolRegistry           # compile_python / eval_math / lookup_path
    ├─ LLMProvider            # Bedrock Converse | Mock (default)
    │       proposes Thought + Action (or Final)
    ├─ Execute tool
    │       │
    │       ├─ ok  → OBSERVATION → continue / final
    │       └─ err → parse stack / SyntaxError (lineno, offset)
    │                 append HEAL_ERROR → rewrite args → retry
    │                 (bounded by max_heals)
    └─ RunResult              # steps, heals, heals_used, answer / failure
```

Key properties:

| Concern | Approach |
|---|---|
| ReAct core | Thought → Action → Observation until final answer |
| Self-heal | Tool exceptions become structured `HEAL_ERROR` traces |
| Compiler API | `compile()` SyntaxError exposes lineno/offset to the healer |
| Bounded loops | `max_heals` caps rewrites → `failed` if still broken |
| LLM portability | `LLMProvider` ABC; Bedrock Converse via `aioboto3`; mock for CI/demos |
| Proof | Demo + tests: fail once → heal → succeed; give up after max heals |

This is complementary to [#3 Strict Pydantic Tool Router](../strict-tool-router/):
that package gates **invalid schemas before execution**; this package recovers
from **runtime / compile failures after execution starts**.

## Why this matters for hiring

Chase builds **production agentic workflows on AWS Bedrock** from a senior DevOps
background. Self-healing loops are the difference between a brittle demo and an
agent that can survive the messy middle of tool use without unsupervised infinite
retries.

## Quick start

From the monorepo root (requires [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --all-packages
export LLM_PROVIDER=mock   # Windows: $env:LLM_PROVIDER="mock"

# Library / CLI demo (broken compile → HEAL_ERROR → rewrite → success)
uv run python -m self_healing_react.demo

# API
uv run uvicorn self_healing_react.main:app --app-dir packages/self-healing-react/src --port 8082

# Tests
uv run pytest packages/self-healing-react/tests -q
```

### Demo: heal after stack trace

```bash
curl -X POST http://127.0.0.1:8082/demo/heal \
  -H "content-type: application/json" \
  -d "{\"scenario\":\"fail_then_heal\"}"
```

Expect `status=succeeded`, `heals_used=1`, and a heal log showing the first
`SyntaxError` plus rewritten `compile_python` arguments.

### Bedrock mode

```bash
export LLM_PROVIDER=bedrock
export AWS_REGION=us-east-1
# plus standard AWS credentials / IAM role
uv run uvicorn self_healing_react.main:app --app-dir packages/self-healing-react/src --port 8082
```

No credentials? Stay on `LLM_PROVIDER=mock` — CI and local demos are designed for that.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `GET` | `/tools` | Registered tools + parameter schemas |
| `POST` | `/run` | Run the self-healing ReAct loop |
| `POST` | `/demo/heal` | Deterministic fail-then-heal hiring demo |

### Library usage

```python
from self_healing_react import SelfHealingReActAgent
from self_healing_react.models import RunRequest

agent = SelfHealingReActAgent()  # mock by default
result = await agent.run(
    RunRequest(goal="mode=fail_then_heal; Compile result=42.")
)
assert result.status.value == "succeeded"
assert result.heals_used == 1
```

## What this proves

1. **Fail once → heal → succeed** — stack/compiler error is actionable input.
2. **Give up after max heals** — no infinite retry loops.
3. **Compiler-aware parsing** — SyntaxError lineno/offset surfaces in `HEAL_ERROR`.
4. **Provider-agnostic core** — Bedrock for production shape, mock for deterministic demos.

## Layout

```
src/self_healing_react/
  main.py         # FastAPI app
  agent.py        # ReAct + heal loop
  tools.py        # demo tools (compile / math / lookup)
  errors.py       # stack / SyntaxError parser
  demo.py         # CLI proof
  config.py
  models.py
  llm/            # Bedrock + mock providers
tests/            # heal, errors, API, LLM factory
```
