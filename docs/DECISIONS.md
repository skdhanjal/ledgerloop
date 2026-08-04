# LedgerLoop - Architecture Decisions

## D-001: LangGraph (Level 1) for orchestration, create_agent (Level 2) for leaves
**Date:** Day 1 | **Status:** Hypothesis - to be tested Days 6-7, revisited Day 29

**Context:** Three abstraction levels exist. The default 2026 answer to "build an
agent" is create_agent + middleware, so a raw StateGraph needs justification.

**Decision:** StateGraph for the outer workflow; create_agent for the Exception
Investigator leaf.

**Reasoning (to be validated):**
1. The pay/hold decision must be a deterministic policy function on variance
   thresholds, not model judgment. A graph puts a hard-coded node in the path.
2. Approval requires a durable pause across days.
3. Line-item matching needs runtime-width parallelism with an exactly-once join.
4. Investigation needs a bounded critique loop (max 2 revisions, then escalate).
5. Control flow must be renderable as a diagram for audit.

**Alternatives considered:** pure create_agent with tools - rejected on (1) and (4);
plain Python state machine + direct API calls - rejected on durability and HITL.

**How I will test this:** Day 6 hand-built investigator vs Day 7 harness version,
compared on tokens, latency and decision accuracy over the same 20 invoices.

**Revisit:** Day 29.

---

## D-002: Synthetic dataset with constructed ground truth
**Date:** Day 1 | **Status:** Accepted

**Decision:** All invoices/POs/receipts from data/generate_invoices.py, seed=42,
ground truth emitted alongside each record.

**Reasoning:** Ground truth must be constructed, not inferred, or the Day 22 golden
dataset is unfalsifiable. Also avoids PII, licensing and OCR entirely, and lets me
control the exception mix.

**Trade-off accepted:** synthetic invoices are cleaner than real ones. Mitigation -
add format noise and an OCR path as a post-30-day extension.

---

## D-003: Free-tier API primary, local model for routers/judges/CI
**Date:** Day 1 | **Status:** Accepted

**Decision:** LEDGERLOOP_MODEL (free-tier API) for extraction and investigation;
LEDGERLOOP_LOCAL_MODEL (Ollama) from Day 21 for routing, judging and CI.

**Reasoning:** Free tiers are rate-limited, not feature-limited. Routers and judges
are high-volume and low-difficulty - exactly where unlimited-but-slow wins. Model
strings live in .env so provider churn is a one-line change.

**Constraint this creates:** must add call-limit middleware on Day 7, before any
unbounded loop exists, or a runaway loop burns the daily quota in minutes.
