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
    strict-tool-router/     # #3 — shipped
    self-healing-react/     # #5 — shipped (this track)
  docs/architecture/        # reserved for #15 system teardowns
  ROADMAP.md                # session build order for agents / Chase
  .github/workflows/        # CI
  pyproject.toml            # uv workspace root
```

Python-first, managed with [uv](https://docs.astral.sh/uv/). Requires Python 3.11+.

```bash
git clone https://github.com/chander4/agentic-portfolio.git
cd agentic-portfolio
uv sync --all-packages
uv run pytest packages/async-orchestrator/tests packages/strict-tool-router/tests packages/self-healing-react/tests -q
```

**Session roadmap:** see [ROADMAP.md](ROADMAP.md) for hireability build order
(`#1` done → `#3` done → `#5` done → `#2` Context Budget Assembler → rest)
and notes for future agents working on glitch at `c:\Users\chase\git\agentic-portfolio`.

## Roadmap (15 projects)

| # | Project | Status | What it demonstrates |
|---|---|---|---|
| **1** | **[Async Agent Orchestrator](packages/async-orchestrator/)** | **Done** | FastAPI + asyncio, 100+ concurrent agents, non-blocking tools, Bedrock-ready LLM layer, graceful tool failure isolation |
| 2 | Context Budget Assembler | **Next** | Pack prompts under token budgets with priority and truncation |
| **3** | **[Strict Pydantic Tool Router](packages/strict-tool-router/)** | **Done** | Schema-first tool args via Pydantic, automatic retry with validation error traces, mock/Bedrock providers |
| 4 | Multi-Agent Supervisor | Later | Planner/worker topology with handoffs and shared scratchpads |
| **5** | **[Self-Healing ReAct](packages/self-healing-react/)** | **Done** | Parse stack/compiler errors; rewrite failing tool calls; bounded heal retries |
| 6 | Retrieval & Memory Fabric | Later | Hybrid retrieval, session memory, and grounding for long-running agents |
| 7 | Eval Harness for Agents | Later | Trajectory scoring, regression suites, CI gates on agent quality |
| 8 | Observability for Agents | Later | Traces, token/cost metrics, tool latency SLOs, incident-ready dashboards |
| 9 | Human-in-the-Loop Desk | Later | Approval queues, escalation policies, and safe resume |
| 10 | Secure Tool Sandbox | Later | Network egress controls, secret redaction, blast-radius limits |
| 11 | Event-Driven Agent Bus | Later | Queue/stream triggered agents with backpressure and DLQs |
| 12 | Cost & Capacity Governor | Later | Budget caps, model routing, and graceful degradation under spend pressure |
| 13 | Agent Integration Test Kit | Later | Contract tests for tools/LLMs with deterministic fixtures |
| 14 | Ops Copilot (IaC + Runtime) | Later | Agents that reason over infra signals without unsupervised mutations |
| 15 | Architecture Teardowns | Later | Written postmortems of real agent system designs (`docs/architecture/`) |

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

## Project #3 highlight

The [Strict Pydantic Tool Router](packages/strict-tool-router/) turns stochastic tool JSON into deterministic actions:

- Every tool declares a Pydantic args model (JSON Schema derived, not hand-rolled)
- Invalid proposals never reach handlers — validation is a hard gate
- Automatic retry appends the `VALIDATION_ERROR` trace so the model can correct itself
- Mock default proves bad→good retry without AWS credentials

```bash
uv run python -m strict_tool_router.demo
uv run uvicorn strict_tool_router.main:app --app-dir packages/strict-tool-router/src --port 8081
curl -X POST http://127.0.0.1:8081/demo/retry -H "content-type: application/json" -d "{\"scenario\":\"bad_then_good\"}"
```

## Project #5 highlight

The [Self-Healing ReAct](packages/self-healing-react/) agent treats tool explosions as recoverable signals:

- ReAct loop (Thought → Action → Observation) with a bounded heal budget
- Parses stack traces and `compile()` SyntaxErrors (lineno/offset) into `HEAL_ERROR` traces
- Rewrites the failing tool call and retries — gives up cleanly after `max_heals`
- Mock default proves fail→heal→succeed without AWS credentials

```bash
uv run python -m self_healing_react.demo
uv run uvicorn self_healing_react.main:app --app-dir packages/self-healing-react/src --port 8082
curl -X POST http://127.0.0.1:8082/demo/heal -H "content-type: application/json" -d "{\"scenario\":\"fail_then_heal\"}"
```

## Contact

- GitHub: [chander4](https://github.com/chander4)
- Location: Atlanta

---

MIT licensed. Built to be forked, run, and reviewed.
