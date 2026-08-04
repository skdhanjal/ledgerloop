"""Nodes. Every one takes state and returns ONLY the keys it changes.

Three of the four are stubs. That is deliberate: today we are proving the wiring,
so nothing here calls a model and nothing here can fail for an interesting reason.
"""

from pathlib import Path

from langgraph.runtime import Runtime
from .state import InvoiceState
from .context import LedgerContext

def intake(state: InvoiceState, runtime: Runtime[LedgerContext]) -> dict:
    """Read the invoice file off disk. The one node that does real work today.

    tenant_id lives in context (supplied per run) AND in state (a durable fact
    about this invoice). A resumed thread must still know whose invoice it is.
    """
    path = Path(state["invoice_path"])

    if not path.exists():
        raise FileNotFoundError(f"No invoice at {path}")

    return {
        "raw_text": path.read_text(encoding="utf-8"),
        "invoice_id": path.stem,
        "tenant_id": runtime.context.tenant_id,
        "audit": [{"node": "intake", "event": "invoice_read", "path": str(path)}]
    }


def extract(state: InvoiceState) -> dict:
    """STUB -> Day 8. Will parse raw_text into validated fields via structured output."""
    assert state.get("raw_text"), "extract ran before intake wrote raw_text"
    return {
        "vendor": "PLACEHOLDER VENDOR",
        "invoice_no": "INV-00000",
        "po_number": "PO-0000",
        "total": 0.0,
    }


def decide(state: InvoiceState, runtime: Runtime[LedgerContext]) -> dict:
    """STUB -> Day 5, but the policy inputs are already injected, not hardcoded."""
    ctx = runtime.context
    po = ctx.po_db.get_po(state.get("po_number", ""))

    if po is None:
        return {
            "decision": "hold",
            "reason": "missing_po",
            "exceptions": [{"code": "missing_po", "severity": "high", "detail": state.get("po_number")}],
            "audit": [{"node": "decide", "event": "po_lookup_failed"}],
        }

    # Day 5 turns this into a real variance comparison using ctx.variance_tolerance
    return {
        "decision": "hold",
        "reason": "stub_always_holds",
        "audit": [{"node": "decide", "event": "policy_stub", "tolerance": ctx.variance_tolerance}],
    }


def post(state: InvoiceState) -> dict:
    """STUB -> Day 19. Will post to the ERP behind an idempotency key."""
    print(f"[post] {state.get('invoice_id')} -> {state.get('decision')}")
    return {"posted": True}
