# #2 — Dynamic Context Budget Assembler

**Status:** implemented (solid start; mock-first)  
**Stack:** FastAPI · Pydantic v2 · deterministic token estimator · optional Bedrock summarizer

## Problem

Agent prompts are a collage: system policy, tool schemas, retrieved docs, chat
history, and the live user turn. Naively concatenating them blows past model
context windows — or worse, silently drops the wrong pieces. Hiring managers
evaluating agent engineers should see whether a candidate treats **context as a
scarce resource with an explicit packing policy**, not a string append.

## Design

```
HTTP (FastAPI) / library API
        │
        ▼
ContextBudgetAssembler
    ├─ Segment[]             # kind, priority, sticky, content
    ├─ estimate_tokens()     # deterministic chars/token (CI-safe)
    ├─ pack by priority ASC  # sticky preferred on ties
    │       ├─ fits      → INCLUDED
    │       ├─ residual  → TRUNCATED (or SUMMARIZED via LLM)
    │       └─ exhausted → DROPPED (non-sticky)
    └─ AssembledContext      # prompt_text + decision ledger
```

Key properties:

| Concern | Approach |
|---|---|
| Hard budget | `used_tokens <= budget_tokens` always |
| Priority | Lower `priority` packed first (0 = must-keep) |
| Sticky | Prefer truncate/summarize over dropping entirely |
| Estimator | Deterministic chars/token — no tiktoken required for demos |
| Optional LLM | Mock/Bedrock summarizer when `allow_summarize=true` |
| Proof | Tests: fit, drop low-priority, truncate sticky, summarize |

## Why this matters for hiring

Chase builds **production agentic workflows on AWS Bedrock** from a senior DevOps
background. Context budgeting is the control plane for cost, latency, and
relevance — the same reliability instincts as capacity planning, applied to
prompts.

## Quick start

From the monorepo root (requires [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --all-packages
export LLM_PROVIDER=mock   # Windows: $env:LLM_PROVIDER="mock"

uv run python -m context_budget_assembler.demo
uv run uvicorn context_budget_assembler.main:app --app-dir packages/context-budget-assembler/src --port 8083
uv run pytest packages/context-budget-assembler/tests -q
```

### Demo: drop low-priority overflow

```bash
curl -X POST http://127.0.0.1:8083/demo/pack \
  -H "content-type: application/json" \
  -d "{\"scenario\":\"overflow_drop_low_priority\",\"budget_tokens\":80}"
```

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `POST` | `/assemble` | Pack arbitrary segments under a budget |
| `POST` | `/demo/pack` | Deterministic hiring scenarios |

## What this proves

1. **Fits under budget** — no silent overshoot.
2. **Drops low priority first** — must-keep system/user survive.
3. **Truncates sticky overflow** — residual tokens are spent, not wasted.
4. **Optional summarize path** — mock/Bedrock can compress a segment to fit.

## Layout

```
src/context_budget_assembler/
  main.py            # FastAPI app
  assembler.py       # packing engine
  tokens.py          # estimator + truncate
  demo_scenarios.py  # hiring demos
  demo.py            # CLI proof
  config.py
  models.py
  llm/               # Bedrock + mock summarizers
tests/
```
