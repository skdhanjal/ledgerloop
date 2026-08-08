"""Per-line three-way matching. One worker per invoice line.

No model call here - this is arithmetic against the purchase order, so it is a
Python function (Day 5's argument). That is also WHY the fan-out can be wide:
forty cheap workers cost nothing, forty model calls would be a rate-limit event.
"""
from typing import TypedDict

from langgraph.runtime import Runtime

from graph.events import ProgressEvent
from graph.state import InvoiceState

MAX_PARALLEL_LINES = 40

class LineMatchInput(TypedDict):
    """The Send payload IS this node's state - not InvoiceState."""
    line_index: int
    line: dict
    po_line: dict | None
    receipt_qty: float | None
    tolerance: float
    total_lines: int


def match_line(state: LineMatchInput, runtime: Runtime[InvoiceState]) -> dict:
    """Compare one invoice line against its PO line and goods receipt."""
    line = state["line"]
    po_line = state.get("po_line")
    idx = state["line_index"]
    lines = state["total_lines"]

    runtime.stream_writer(ProgressEvent(stage="match", 
        label=f"Matching line {idx+1} of {lines}", done=idx+1, total=lines).model_dump())

    if po_line is None:
        return {"line_matches": [{
            "line_index": idx, "sku": line.get("sku"),
            "status": "no_po_line", "price_variance": 0.0,
            "qty_ratio": 1.0,
            "detail": f"SKU {line.get('sku')} is not on the purchase order",
        }]}

    # --- unit of measure: the case that breaks naive matchers both ways ---
    uom = (line.get("unit_of_measure") or "").upper()
    units_per = 12 if uom.startswith("CASE") else 1
    inv_qty_units = line["quantity"] * units_per
    inv_unit_price = line["unit_price"] / units_per

    po_price = po_line["unit_price"]
    variance = (inv_unit_price - po_price) / po_price if po_price else 0.0

    received = state.get("receipt_qty")
    qty_ratio = (received / inv_qty_units
                 if received is not None and inv_qty_units else 1.0)

    status = "ok"
    if variance > state["tolerance"]:
        status = "price_variance"
    elif qty_ratio < 1.0:
        status = "short_shipment"

    return {"line_matches": [{
        "line_index": idx,
        "sku": line.get("sku"),
        "status": status,
        "price_variance": round(variance, 4),
        "qty_ratio": round(qty_ratio, 4),
        "uom_normalised": units_per > 1,
        "detail": (f"invoiced {inv_unit_price:.2f}/unit vs PO {po_price:.2f}"
                   if status == "price_variance" else
                   f"received {qty_ratio:.0%} of invoiced" if status == "short_shipment"
                   else "matched"),
    }]}
