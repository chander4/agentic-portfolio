# Portfolio session roadmap

Actionable build order for future Project sessions and agents working in this
monorepo. No fake completion dates — status only.

## Session notes (read first)

- **Work here:** `c:\Users\chase\git\agentic-portfolio` (public:
  [chander4/agentic-portfolio](https://github.com/chander4/agentic-portfolio))
- **Worker:** Chase's Windows PC / glitch self-hosted Cursor worker
- **LLM default:** `LLM_PROVIDER=mock` for demos and CI; Bedrock Converse is the
  production-shaped provider path (credentials optional)
- **Package style:** mirror `packages/async-orchestrator` — `pyproject.toml`,
  `src/<pkg>/`, FastAPI or clear library API, runnable demo, tests, hiring-focused
  README (problem / design / how to run / what it proves)
- **Workspace:** `uv` workspace root; add each project under `packages/` and keep
  CI green (`ruff` + `pytest`)

## Hireability path (priority order)

| Order | # | Project | Status | Notes |
|---|---|---|---|---|
| 1 | **1** | [Async Agent Orchestrator](packages/async-orchestrator/) | **Done** | Concurrent agents, non-blocking tools, mock/Bedrock |
| 2 | **3** | [Strict Pydantic Tool Router](packages/strict-tool-router/) | **Done** | Schema gate + retry-with-trace |
| 3 | **5** | [Self-Healing ReAct](packages/self-healing-react/) | **Done** | Stack/compiler heal loop with bounded retries |
| 4 | **2** | [Context Budget Assembler](packages/context-budget-assembler/) | **Done** | Priority pack + truncate/summarize under hard budget |
| 5+ | 4, 6–15 | Remaining projects | **Later** | See backlog below — **#4 Multi-Agent Supervisor** is next |

After #2 merges, the next session should start **#4 Multi-Agent Supervisor** unless
Chase redirects.

## Full backlog (one-liners)

| # | Project | Status | One-liner |
|---|---|---|---|
| 1 | Async Agent Orchestrator | Done | Event-loop concurrency for 100+ tool-using agents |
| 2 | Context Budget Assembler | Done | Assemble RAG/history/tool context under a hard token budget |
| 3 | Strict Pydantic Tool Router | Done | Force tool args through Pydantic; retry on validation errors |
| 4 | Multi-Agent Supervisor | Next | Planner/worker topology with handoffs and shared scratchpads |
| 5 | Self-Healing ReAct | Done | ReAct loop that diagnoses and repairs failed steps |
| 6 | Retrieval & Memory Fabric | Later | Hybrid retrieval + session memory for long-running agents |
| 7 | Eval Harness for Agents | Later | Trajectory scoring and CI gates on agent quality |
| 8 | Observability for Agents | Later | Traces, token/cost metrics, tool latency SLOs |
| 9 | Human-in-the-Loop Desk | Later | Approval queues, escalation, safe resume |
| 10 | Secure Tool Sandbox | Later | Egress controls, secret redaction, blast-radius limits |
| 11 | Event-Driven Agent Bus | Later | Queue/stream triggered agents with backpressure and DLQs |
| 12 | Cost & Capacity Governor | Later | Budget caps, model routing, degrade under spend pressure |
| 13 | Agent Integration Test Kit | Later | Contract tests for tools/LLMs with deterministic fixtures |
| 14 | Ops Copilot (IaC + Runtime) | Later | Reason over infra signals without unsupervised mutations |
| 15 | Architecture Teardowns | Later | Written postmortems in `docs/architecture/` |

## Definition of done (per package)

1. Lives under `packages/<name>/` and is a `uv` workspace member
2. Mock LLM by default; Bedrock provider stub or full Converse path
3. Runnable demo + tests that prove the hiring claim
4. Package README + root README / this roadmap status updated
5. CI covers the new package
