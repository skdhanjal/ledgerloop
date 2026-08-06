"""Nodes for the forked graph. New: extract retries, investigate, escalate."""
import re
from pathlib import Path

from langgraph.runtime import Runtime

from .memory import (format_for_prompt, recall_vendor, remember_resolution)
from .context import LedgerContext
from .policy import PolicyInput, evaluate
from .state import InvoiceState

MONEY = r"([\d,]+\.\d{2})"


def intake(state: InvoiceState, runtime: Runtime[LedgerContext]) -> dict:
    path = Path(state["invoice_path"])
    
    if not path.exists():
        raise FileNotFoundError(f"No invoice at {path}")

    return {
        "raw_text": path.read_text(encoding="utf-8"),
        "invoice_id": path.stem,
        "tenant_id": runtime.context.tenant_id,
        "audit": [{"node": "intake", "event": "invoice_read"}],
    }


def extract(state: InvoiceState) -> dict:
    """Still not a model - regex today, structured output on Day 8.

    Increments its own attempt counter so the router can see the loop count.
    """
    attempt = state.get("extract_attempts", 0) + 1
    text = state["raw_text"]

    po = re.search(r"PO Reference:\s*(\S+)", text)
    total = re.search(rf"Total Due:\s*{MONEY}", text)
    subtotal = re.search(rf"Subtotal:\s*{MONEY}", text)
    tax = re.search(rf"Tax \(18%\):\s*{MONEY}", text)

    ok = all([po, total, subtotal, tax])
    if not ok:
        return {
            "extract_attempts": attempt,
            "extract_ok": False,
            "audit": [{"node": "extract", "event": "parse_failed", "attempt": attempt}],
        }

    f = lambda m: float(m.group(1).replace(",", ""))
    sub, tx, tot = f(subtotal), f(tax), f(total)

    return {
        "extract_attempts": attempt,
        "extract_ok": True,
        "po_number": po.group(1),
        "total": tot,
        "subtotal": sub,
        "arithmetic_ok": abs((sub + tx) - tot) < 0.01,
        "audit": [{"node": "extract", "event": "parsed", "attempt": attempt}],
    }


def decide(state: InvoiceState, runtime: Runtime[LedgerContext]) -> dict:
    """Gather the facts, hand them to the pure policy function, record the result."""
    ctx = runtime.context
    po = ctx.po_db.get_po(state.get("po_number", ""))
    receipt = ctx.po_db.get_receipt(state.get("po_number", ""))

    # Day 14 replaces this with real per-line matching; today, whole-invoice.
    # after — net vs net
    
    if po:
        po_total = sum(l["quantity"] * l["unit_price"] for l in po["lines"])
        invoice_net = state.get("subtotal") or state.get("total", 0.0)
        variance = (invoice_net - po_total) / po_total if po_total else 0.0
        # variance = (state["total"] - po_total) / po_total if po_total else 0.0
        received = (sum(l["quantity_received"] for l in receipt["lines"])
                    / sum(l["quantity"] for l in po["lines"])) if receipt else 1.0
    else:
        variance, received = 0.0, 1.0

    outcome = evaluate(
        PolicyInput(
            total=state.get("total", 0.0),
            po_exists=po is not None,
            price_variance=max(variance, 0.0),
            qty_received_ratio=received,
            is_duplicate=False,               # Day 6 adds the duplicate tool
            arithmetic_ok=state.get("arithmetic_ok", True),
        ),
        tolerance=ctx.variance_tolerance,
        max_auto_approve=ctx.max_auto_approve,
    )
    return {
        "decision": outcome.decision,
        "reason": outcome.reason,
        "exceptions": outcome.exceptions,
        "audit": [{"node": "decide", "event": "policy_evaluated", "decision": outcome.decision, "reason": outcome.reason}],
    }


def investigate(state: InvoiceState) -> dict:
    """STUB -> Day 6, where this becomes a hand-built ReAct agent."""
    codes = [e["code"] for e in state.get("exceptions", [])]
    return {
        "notes": [f"investigation stub: {', '.join(codes) or 'no exceptions'}"],
        "audit": [{"node": "investigate", "event": "stub"}],
    }


def escalate(state: InvoiceState) -> dict:
    """The designed exit when the semantic brake fires. Never a crash."""
    return {
        "decision": "hold",
        "reason": "escalated_extraction_failed",
        "exceptions": [{"code": "extraction_failed", "severity": "high",
                        "detail": f"gave up after {state.get('extract_attempts')} attempts"}],
        "audit": [{"node": "escalate", "event": "handed_to_human"}],
    }


def post(state: InvoiceState) -> dict:
    print(f"[post] {state.get('invoice_id')} -> {state.get('decision')}")
    return {"posted": True, "audit": [{"node": "post", "event": "posted"}]}


"""Investigator wiring, now with recall before and a write after."""
def investigate_with_memory_factory(agent):
    """agent is the create_agent instance from Day 8."""

    def investigate(state, runtime: Runtime[LedgerContext]) -> dict:
        tenant = runtime.context.tenant_id
        vendor = state.get("vendor", "")

        # --- recall: what do we already know about this vendor? ---
        memories = recall_vendor(
            runtime.store, tenant, vendor,
            query=state.get("reason", "exception"), limit=3)

        opening = (
            f"Invoice {state.get('invoice_id')} was flagged: "
            f"{', '.join(e['code'] for e in state.get('exceptions', []))}.\n"
            f"Vendor: {vendor}\nPO reference: {state.get('po_number')}\n"
            f"Invoice total: {state.get('total')}\n\n"
            f"{format_for_prompt(memories)}\n\nInvestigate and report."
        )

        print("opening", opening)

        result = agent.invoke({"messages": [{"role": "user", "content": opening}]})
        verdict = result.get("structured_response")

        if verdict is None:
            return {"investigation": "no structured verdict", "audit": [{"node": "investigate", "event": "no_verdict"}]}

        # --- write: only a RESOLUTION, and only once we have one ---
        # From Day 11 this moves behind the human approval gate: a memory
        # written from an unreviewed verdict is a confident guess that every
        # future invoice from this vendor will inherit.
        if verdict.confidence >= 0.7 and state.get("exceptions"):
            remember_resolution(
                runtime.store, tenant, vendor,
                exception_code=state["exceptions"][0]["code"],
                root_cause=verdict.root_cause,
                resolution=verdict.recommendation,
                invoice_id=state.get("invoice_id", ""),
            )

        return {
            "investigation": verdict.root_cause,
            "verdict": verdict.model_dump(),
            "notes": [f"{len(memories)} memories recalled"],
            "audit": [{"node": "investigate", "event": "verdict", "memories_used": len(memories), "confidence": verdict.confidence}],
        }

    return investigate


