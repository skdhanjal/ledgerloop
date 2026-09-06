# LedgerLoop — Decisions Log

One entry per trade-off made along the way, written the day it's made. This is the raw material the Day-30 case study is written from — nothing in that write-up should say anything not traceable back to an entry here.

---

## Day 1 — Graph runtime vs. agent harness (initial criteria, revisit Day 30)

**Decision.** Reach for a raw `StateGraph` (LangGraph) instead of a pre-built agent loop wherever the control flow needs one of: a bounded, structured investigation loop; parallel line-item fan-out with a real deferred join; a durable, multi-day human-approval pause; or a decision that must be model-blind by construction. Reach for `langchain.agents.create_agent` (a harness *on top of* LangGraph) for the investigator itself, since that's the one place in the pipeline where "call tools, reason, produce structured output" is the whole job and the framework's built-in structured-output enforcement and middleware hooks earn their keep.

**Why.** The graph is chosen when a loop can't express the required control flow — not by default. LedgerLoop's pipeline (intake → extract → match/fan-out → policy → investigate → approve → post) has at least three places a plain agent loop cannot express safely: the deferred join (Day 14), the durable interrupt (Day 11), and the model-blind policy gate (Day 5). The investigator subgraph is the one node where a harness is strictly better than hand-rolling.

**Revisit.** Day 13 measures a supervisor/swarm/hierarchical alternative against the single-investigator design with real numbers. Day 30 revisits this whole entry with the finished system in view.

---

## Day 1 — New dedicated GCP project, not an existing one

**Decision.** Created a new project (`ledgerloop-880ac9`) rather than reusing the `sentinel-desk-dev` project already active in this machine's `gcloud` config.

**Why.** Keeps billing, IAM, and the eventual audit trail (Day 26/28) scoped cleanly to this system. The existing project carries unrelated work and unrelated budget alerts.

**Details.** Billing account `01D6C8-3B6B7B-19CD26` linked. A $20/month budget alert (`ledgerloop-monthly`, 50/90/100% thresholds) was created on Day 1 itself, before any resource that spends money exists — per Appendix A's "watch the cloud bill from Day 9" rule, done three days early since project creation is when the risk starts, not when Cloud SQL lands.

---

## Day 1 — Package name is `ledgerloop`, not `agent-service`

**Decision.** The Python project inside `agent-service/` is named and imported as `ledgerloop` (`src/ledgerloop/...`), matching every CLI invocation in the master doc (`python -m ledgerloop.cli`, `ledgerloop.data.generate`, etc.). The directory is still called `agent-service/` to match the monorepo layout the doc uses for Terraform/deployment purposes — the directory name and the Python package name are deliberately different things.

---

## Day 1 — `langchain-openai` is a real agent-service dependency, despite one doc table's annotation

**Decision.** Installed `langchain-openai` in `agent-service`'s own dependency graph, even though the doc's §1.10.1 pinned-baseline table annotates it "used only by the gateway's own config path, never by service code." Did **not** install `langchain-google-genai` in agent-service.

**Why.** The gateway (Day 4) exposes an OpenAI-compatible endpoint for every tier (`fast`/`balanced`/`deep`/`judge`), regardless of which real provider backs a given tier. The standard way to speak that protocol from LangChain is `langchain_openai.ChatOpenAI` pointed at the gateway's `base_url` with a virtual key — that's calling *the gateway*, not a provider SDK, so it doesn't violate C10 or trip the Day-4 `ruff` gateway-guard rule (which bans importing `openai`/`google.generativeai` directly in service code, not the LangChain wrapper). Since every tier is reached through the same OpenAI-shaped endpoint, `langchain-google-genai` has no call site in agent-service at all — the multi-provider fallback is entirely the gateway's concern, invisible to the service. §1.10.2's literal `uv add` command (the one actually meant to be run) already omits both packages from agent-service; this entry just makes explicit *why* one of them still needed adding.

---

## Day 2 — Synthetic data: file layout, invoice-count interpretation, exception vocabulary

**Decision.** Three things the doc's Day 2 build commands left ambiguous, resolved before writing the generator:

1. **Output layout is one JSON file per document**, not one JSONL file per tenant per doc-type: `data/base/<tenant_id>/{invoices,purchase_orders,goods_receipts,ground_truth}/<DOC-ID>.json`, plus `<tenant_id>/tenant.json` and a top-level `manifest.json`.
2. **`--invoices 150` means the total across all tenants**, split as evenly as possible (3 tenants → 50 each), not 150 per tenant.
3. **Exception types seeded by the generator are exactly the vocabulary Day 5's policy cascade will use**: `duplicate`, `missing_po`, `arithmetic_error`, `price_variance`, `short_shipment`, `over_ceiling`, plus `clean`.

**Why.** (1) A later `ledgerloop.cli run --tenant acme --invoice INV-0007` (Day 6) needs to open a single invoice by id directly — a JSONL layout would require scanning or a separate index. The trade is more files (556 for the committed set) in exchange for direct lookup. (2) Today's generator produces the *base* fixture set; the doc's own phase map puts the larger stratified and adversarial sets on Days 17 and 23, so keeping the base set closer to 150 than 450 documents matches that scoping. (3) Seeding exactly Day 5's rule vocabulary now means every rule in that cascade has real, labeled test cases the day it's implemented, instead of the generator and the policy engine drifting into two different ideas of what an "exception" is.

**Details.** All three were confirmed with the user via `AskUserQuestion` before implementation (both had a clearly better default, but both shape how every later day reads this data, so worth a direct check rather than a silent judgment call). Resolved counts for the committed `seed=42` set: 150 invoices (50/tenant), mix `{clean: 90, duplicate: 12, missing_po: 12, price_variance: 9, over_ceiling: 9, arithmetic_error: 9, short_shipment: 9}`.

---
