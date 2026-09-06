# LedgerLoop

A durable, multi-tenant **accounts-payable exception agent** built on [LangGraph](https://github.com/langchain-ai/langgraph) — extraction, three-way matching, a deterministic policy gate, a bounded investigator agent, human-in-the-loop approval, and idempotent ERP posting, deployed on GCP behind a self-hosted LLM gateway.

Invoices arrive as attacker-controlled documents. They're extracted against a schema, matched against purchase orders and goods receipts, and judged by a pure, model-blind policy function that emits pay / hold / reject. Clean invoices auto-approve. Exceptions are investigated by a single tool-using agent and routed to a human, whose approval can pause the workflow for days and must survive a process restart. Approved payments post to an ERP exactly once.

## Design principles

- **A pure policy function is the only thing that can authorize payment.** It never receives model-generated output — enforced by a signature-inspection test, not convention.
- **Ground truth in synthetic data is constructed, never inferred.**
- **Human approval survives a crash or a multi-day wait** via a durable interrupt, never an in-memory pause.
- **Tenant isolation is enforced at every layer** that touches data — store, database, API — not just at login.

## Architecture at a glance

| Layer | What it does |
|---|---|
| Ingestion & extraction | Structured-output extraction against a Pydantic schema, with a bounded retry budget and a designed escalate path |
| Matching | Pure-Python three-way match (invoice × PO × goods receipt), runtime-width fan-out with a deferred join — zero model calls |
| Policy engine | A pure `evaluate(PolicyInput) → PolicyOutcome` function — the single load-bearing safety property of the system |
| Exception investigator | One framework-based agent (`langchain.agents.create_agent`), mounted as a subgraph with a narrow state boundary |
| Human-in-the-loop | `interrupt()`-based approval, edit-and-rerun that re-enters the pipeline at extraction rather than patching the decision |
| LLM gateway | A dedicated LiteLLM proxy — the only path to any model provider, with tiered routing and cross-provider fallback |
| Guardrails | Layered prompt-injection defense: regex scan → classifier → untrusted-document framing → tool allowlist |
| Multi-tenancy | Federated auth (OIDC/SAML), RBAC, and Postgres row-level security as an independent backstop |

Full design rationale, invariants, and the day-by-day build plan live in the project's internal build documentation (not part of this repo — see below).

## Repository layout

```
agent-service/   Python service — the LangGraph app, policy engine, tools, API (FastAPI)
frontend/        React + TypeScript + Vite operator console (from Day 21)
litellm-proxy/   Self-hosted LLM gateway config (from Day 4)
infra/           Terraform — one reusable Cloud Run module, instantiated per service
evals/           Evaluation harness and golden datasets
data/            Generated synthetic invoices, POs, and receipts (gitignored — regenerated from a seed)
docs/            DECISIONS.md and BENCH.md — the project's running decision log and benchmark numbers
```

## Status

Early build — see [`docs/DECISIONS.md`](docs/DECISIONS.md) for the trade-offs made so far and [`docs/BENCH.md`](docs/BENCH.md) for measured numbers as they accumulate. Every tagged release (`v0`–`v4`) marks a milestone with its own passing test suite and benchmark table.

## Stack

Python 3.12 · `uv` · LangGraph · LangChain · FastAPI · Postgres · LiteLLM · Terraform · GCP Cloud Run · React + TypeScript + Vite

## Note on scope

This repo tracks the production system: application code, infrastructure, and the project's decision/benchmark logs. Personal build notes and study material aren't part of it by design.
