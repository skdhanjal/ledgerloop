"""Fan-out and the deferred reconciler."""
from langgraph.runtime import Runtime
from langgraph.types import Send

from graph.events import ProgressEvent

from .matching import MAX_PARALLEL_LINES
from .state import InvoiceState


def fan_out_lines(state: InvoiceState, po_db, tolerance: float) -> list[Send]:
    """One Send per invoice line. Width is runtime data, so it must be capped.

    Each worker gets a SMALL private payload - not the invoice, not the message
    history. Thirty workers carrying 8 KB of state each is 240 KB of pointless
    serialization per super-step.
    """
    lines = (state.get("fields") or {}).get("lines", [])[:MAX_PARALLEL_LINES]
    po = po_db.get_po(state.get("po_number", "")) or {"lines": []}
    receipt = po_db.get_receipt(state.get("po_number", "")) or {"lines": []}

    po_by_sku = {l["sku"]: l for l in po["lines"]}
    recv_by_sku = {l["sku"]: l["quantity_received"] for l in receipt["lines"]}

    return [
        Send("match_line", {
            "line_index": i,
            "line": line,
            "po_line": po_by_sku.get(line.get("sku")),
            "receipt_qty": recv_by_sku.get(line.get("sku")),
            "tolerance": tolerance,
            "total_lines": len(lines)
        })
        for i, line in enumerate(lines)
    ]


def reconcile(state: InvoiceState, runtime: Runtime[InvoiceState]) -> dict:
    """Aggregate every line result into invoice-level facts.

    MUST be registered with defer=True. Without it this runs once per branch
    that reaches it, each time with partial data - and the policy router may
    approve a payment computed from a third of the invoice.
    """
    matches = state.get("line_matches", [])
    
    if not matches:
        return {"reconciled": False,
                "audit": [{"node": "reconcile", "event": "no_lines"}]}

    runtime.stream_writer(ProgressEvent(stage="reconcile",
                        label=f"reconciling {len(matches)} lines",
                        done=len(matches), total=len(matches)).model_dump())            

    worst_variance = max((m["price_variance"] for m in matches), default=0.0)
    worst_qty = min((m["qty_ratio"] for m in matches), default=1.0)
    failing = [m for m in matches if m["status"] != "ok"]
    uom_lines = [m["line_index"] for m in matches if m.get("uom_normalised")]

    return {
        "reconciled": True,
        "worst_price_variance": worst_variance,
        "worst_qty_ratio": worst_qty,
        "failing_lines": [m["line_index"] for m in failing],
        "audit": [{"node": "reconcile", "event": "reconciled",
                   "lines": len(matches), "failing": len(failing),
                   "uom_normalised_lines": uom_lines}],
    }
