# Agentic Portfolio — Chase Anderson

Senior DevOps engineer building toward **Agentic AI Engineer** roles. This monorepo is a public body of work: production-shaped systems around async orchestration, tool-using agents, evaluation, and AWS Bedrock — not toy chat wrappers.

## Positioning

I operate at the intersection of **infrastructure reliability** and **agentic workflows**. Day-to-day that means shipping systems that call models (especially **AWS Bedrock**), invoke tools safely under concurrency, and fail closed when providers or tools misbehave. This portfolio makes that skill set reviewable: each package is runnable, tested, and honest about what it proves.

No invented employers. No screenshot-only demos. Code first.

## Repository layout

```
agentic-portfolio/
  packages/                 # one package per portfolio project
    async-orchestrator/     # #1 — shipped
  docs/architecture/        # reserved for #15 system teardowns
  .github/workflows/        # CI
  pyproject.toml            # uv workspace root
```

Python-first, managed with [uv](https://docs.astral.sh/uv/). Requires Python 3.11+.

```bash
git clone https://github.com/chander4/agentic-portfolio.git
cd agentic-portfolio
uv sync --all-packages
uv run pytest packages/async-orchestrator/tests -q
```

## Roadmap (15 projects)

| # | Project | Status | What it demonstrates |
|---|---|---|---|
| **1** | **[Async Agent Orchestrator](packages/async-orchestrator/)** | **Done** | FastAPI + asyncio, 100+ concurrent agents, non-blocking tools, Bedrock-ready LLM layer, graceful tool failure isolation |
| 2 | Tool Gateway & Policy Engine | Planned | AuthZ, allowlists, rate limits, and audit trails in front of agent tools |
| 3 | Bedrock Agent Runtime Adapter | Planned | Production Converse/Agents wiring, retries, idempotency, cost attribution |
| 4 | Multi-Agent Supervisor | Planned | Planner/worker topology with handoffs and shared scratchpads |
| 5 | Durable Agent Workflows | Planned | Checkpointing, resume-after-crash, exactly-once tool side effects |
| 6 | Retrieval & Memory Fabric | Planned | Hybrid retrieval, session memory, and grounding for long-running agents |
| 7 | Eval Harness for Agents | Planned | Trajectory scoring, regression suites, CI gates on agent quality |
| 8 | Observability for Agents | Planned | Traces, token/cost metrics, tool latency SLOs, incident-ready dashboards |
| 9 | Human-in-the-Loop Desk | Planned | Approval queues, escalation policies, and safe resume |
| 10 | Secure Tool Sandbox | Planned | Network egress controls, secret redaction, blast-radius limits |
| 11 | Event-Driven Agent Bus | Planned | Queue/stream triggered agents with backpressure and DLQs |
| 12 | Cost & Capacity Governor | Planned | Budget caps, model routing, and graceful degradation under spend pressure |
| 13 | Agent Integration Test Kit | Planned | Contract tests for tools/LLMs with deterministic fixtures |
| 14 | Ops Copilot (IaC + Runtime) | Planned | Agents that reason over infra signals without unsupervised mutations |
| 15 | Architecture Teardowns | Planned | Written postmortems of real agent system designs (`docs/architecture/`) |

## Project #1 highlight

The [Async Agent Orchestrator](packages/async-orchestrator/) is the foundation everything else builds on:

- Concurrent agent tasks on a single event loop (proven at 100+)
- Awaitable tool calls with per-tool timeouts
- Failures contained — bad tools/LLM errors do not kill siblings
- `LLM_PROVIDER=mock` for credential-free demos; `bedrock` for the production path
- Side-by-side demo showing why blocking `time.sleep` / sync SDKs destroy throughput

```bash
uv run uvicorn async_orchestrator.main:app --app-dir packages/async-orchestrator/src --port 8080
curl -X POST "http://127.0.0.1:8080/demo/concurrency?count=100&sleep_seconds=0.05"
```

## Contact

- GitHub: [chander4](https://github.com/chander4)
- Location: Atlanta

---

MIT licensed. Built to be forked, run, and reviewed.
