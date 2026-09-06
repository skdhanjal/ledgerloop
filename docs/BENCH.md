# LedgerLoop — Benchmarks

Every number that gets reported at a milestone lands here first, on the day it's measured. Nothing in this file is estimated — if a row exists, something was actually run to produce it.

---

## Day 1 — Environment & dependency graph

- `uv lock` resolved **89 packages** (production) + dev group, **zero conflicts**, against Python 3.12.14.
- Exact resolved core versions: `langgraph==1.2.11`, `langchain==1.4.0`, `langchain-core==1.6.2`, `pydantic==2.13.5`, `fastapi==0.141.1`, `sse-starlette==3.4.11`, `psycopg==3.3.5`, `fastembed==0.8.0`, `faker==40.38.0`, `langsmith==0.12.2` — all match the doc's pinned floor/ceiling ranges exactly.
- `scripts/check_versions.py`: **PASS** (all expected prefixes matched).
- `terraform init` against the real GCS backend (`gs://ledgerloop-880ac9-tfstate`): **PASS**, zero resources planned (correct — nothing needs one yet).
- GCP project `ledgerloop-880ac9` created, billing linked, $20/mo budget alert active.

---

<!-- Day 2+ tables append below, one per milestone/day as measured. -->
