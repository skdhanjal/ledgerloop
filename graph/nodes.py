"""Nodes. Every one takes state and returns ONLY the keys it changes.

Three of the four are stubs. That is deliberate: today we are proving the wiring,
so nothing here calls a model and nothing here can fail for an interesting reason.
"""

from pathlib import Path
from .state import InvoiceState

def intake(state: InvoiceState) -> dict:
    """Read the invoice file off disk. The one node that does real work today."""
    path = Path(state["invoice_path"])
    if not path.exists():
        raise FileNotFoundError(f"No invoice at {path}")

    return {
        "raw_text": path.read_text(encoding="utf-8"),
        "invoice_id": path.stem,
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


def decide(state: InvoiceState) -> dict:
    """STUB -> Day 5. Will become a deterministic policy router on variance."""
    return {"decision": "hold", "reason": "stub_always_holds"}


def post(state: InvoiceState) -> dict:
    """STUB -> Day 19. Will post to the ERP behind an idempotency key."""
    print(f"[post] {state.get('invoice_id')} -> {state.get('decision')}")
    return {"posted": True}
