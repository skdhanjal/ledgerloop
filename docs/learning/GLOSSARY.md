# LedgerLoop — Glossary

Running list of every tool, pattern, and term introduced along the build, in the order they first showed up. Alphabetical index below the table for quick lookup; each entry links back to the day it was introduced, where the full "why" lives.

| Term | One-line definition | First seen |
|---|---|---|
| `uv` | A fast Python package/project manager (replaces `pip`+`venv`+`poetry`-style tooling) that resolves a whole dependency graph and writes a lockfile | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Lockfile (`uv.lock`) | A file recording the *exact* resolved version of every package (direct and transitive) so `uv sync` reproduces the identical environment anywhere | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Upper-bounded version pin (`>=X,<Y`) | A dependency constraint with both a floor and a ceiling, so a routine `sync` can't silently pull in a breaking major/minor version | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| `src/` layout | A Python project layout where importable code lives under `src/<package>/` instead of directly in the repo root, preventing accidental imports of uninstalled code | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| `ruff` | A fast Python linter (replaces tools like `flake8`/`isort`) that can also enforce custom banned-import rules | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Banned-API lint rule (`TID251`) | A `ruff` rule that fails the build if specific modules are imported anywhere in the codebase — used here to physically prevent any service from importing a provider SDK directly | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| LangGraph | A low-level, durable graph runtime for building stateful agents: nodes, edges, channels, checkpointing, and human-in-the-loop pauses, all built in | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Pregel-style execution | A "bulk synchronous parallel" execution model (from Google's graph-processing paper) where a graph runs in discrete super-steps: every active node runs, writes updates, then the next super-step begins | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| `langchain.agents.create_agent` | A pre-built agent harness (ReAct-style: reason → call tool → observe → repeat) built on top of LangGraph, handling tool-call bookkeeping and structured output for you | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Terraform | An infrastructure-as-code tool: you declare desired cloud resources in `.tf` files, and it computes and applies the diff against reality | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Terraform state | Terraform's record of what it last created, used to compute future diffs — must be stored somewhere durable and lockable, never just on a laptop | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Terraform backend | The storage location for Terraform state (here: a GCS bucket) — separate from the resources Terraform manages | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Terraform module | A reusable, parameterized bundle of resource definitions — written once, instantiated multiple times with different inputs | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| GCP project | The top-level container for billing, IAM, and resources in Google Cloud — isolation boundary between unrelated workloads | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Artifact Registry | GCP's managed storage for container images (and other build artifacts) | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Billing budget alert | A GCP-native notification that fires at spend thresholds (e.g. 50/90/100% of a monthly cap) — visibility, not an enforced ceiling | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Cloud Run | GCP's serverless container platform — deploy a container, it autoscales on request volume, and can scale to zero when idle | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |
| Monorepo | A single repository holding multiple independently-deployable services/components (here: agent-service, frontend, litellm-proxy, infra) | [Day 1](day-01-graph-runtime-monorepo-terraform-bootstrap.md) |

## Alphabetical index

Artifact Registry · Banned-API lint rule · Billing budget alert · Cloud Run · GCP project · LangGraph · `langchain.agents.create_agent` · Lockfile · Monorepo · Pregel-style execution · `ruff` · `src/` layout · Terraform · Terraform backend · Terraform module · Terraform state · Upper-bounded version pin · `uv`
