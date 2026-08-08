"""The investigator's tools.

Built by a factory so the PO database is INJECTED, not imported. That keeps
Day 4's boundary intact (dependencies live in context, never in state) and
makes every tool testable against a fake with no monkeypatching.

Alternative worth knowing: a tool may declare a `runtime: ToolRuntime`
parameter and read `runtime.context` directly. The factory is used here
because it keeps the dependency explicit at the call site.
"""
import json
from pathlib import Path
from langgraph.config import get_stream_writer
from langchain.tools import tool

from graph.events import ProgressEvent

MAX_CHARS = 600          # tool output lives in the message channel forever

def make_tools(po_db, invoice_index: dict[str, list[dict]]):
    """invoice_index: vendor -> list of previously seen invoices for that tenant."""

    @tool
    def lookup_po(po_number: str) -> str:
        """Fetch a purchase order by its number.

        Returns the vendor and every line with SKU, ordered quantity and agreed
        unit price. Use this to check whether an invoice's prices and quantities
        match what was actually ordered.
        Returns NOT_FOUND if no purchase order with that number exists.
        """
        get_stream_writer()(ProgressEvent(stage="investigate", label=f"checking {po_number}..").model_dump())
        po = po_db.get_po(po_number)
        if po is None:
            return f"NOT_FOUND: no purchase order {po_number}"
        lines = "; ".join(
            f"{l['sku']} qty={l['quantity']} unit_price={l['unit_price']:.2f}"
            for l in po["lines"])
        return f"PO {po_number} vendor={po['vendor']} | {lines}"[:MAX_CHARS]

    @tool
    def lookup_receipt(po_number: str) -> str:
        """Fetch the goods receipt for a purchase order.

        Returns the quantity actually RECEIVED per SKU, which may be less than
        the quantity ordered. Use this to detect short shipments: an invoice
        billing for more than was received should not be paid in full.
        Returns NOT_FOUND if nothing was received against that purchase order.
        """
        get_stream_writer()(ProgressEvent(stage="investigate", label=f"checking receipt for {po_number}..").model_dump())

        r = po_db.get_receipt(po_number)
        if r is None:
            return f"NOT_FOUND: no goods receipt for {po_number}"
        lines = "; ".join(
            f"{l['sku']} received={l['quantity_received']}" for l in r["lines"])
        return f"Receipt for {po_number} | {lines}"[:MAX_CHARS]

    @tool
    def check_duplicate_invoice(vendor: str, invoice_number: str) -> str:
        """Check whether this vendor already sent an invoice with this invoice number.

        A vendor plus invoice number pair should appear only once. A match means
        this is a duplicate submission and must NOT be paid again.
        Returns DUPLICATE with the earlier date, or UNIQUE if not seen before.
        """
        get_stream_writer()(ProgressEvent(stage="investigate", label=f"checking duplicate invoice({invoice_number}) for {vendor}..").model_dump())

        for prior in invoice_index.get(vendor, []):
            if prior.get("invoice_number") == invoice_number:
                return (f"DUPLICATE: {vendor} already submitted {invoice_number} "
                        f"on {prior['date']}")
        return f"UNIQUE: no earlier invoice {invoice_number} from {vendor}"

    @tool
    def vendor_history(vendor: str) -> str:
        """Summarise our recent invoice history with a vendor.

        Returns how many invoices we have seen and how many were previously
        held. Use this for context when deciding whether an exception is a
        one-off or a recurring pattern with this supplier.
        """
        get_stream_writer()(ProgressEvent(stage="investigate", label=f"checking vendor history of {vendor}..").model_dump())

        prior = invoice_index.get(vendor, [])
        if not prior:
            return f"NO_HISTORY: first invoice from {vendor}"
        held = sum(1 for p in prior if p.get("expected_decision") != "auto_approve")
        return (f"{vendor}: {len(prior)} prior invoices, {held} previously held")

    return [lookup_po, lookup_receipt, check_duplicate_invoice, vendor_history]


def build_invoice_index(path: Path = Path("data/generated/invoices.json")) -> dict:
    """Group generated invoices by vendor. Stands in for an AP history table."""
    index: dict[str, list[dict]] = {}
    for inv in json.loads(path.read_text()):
        index.setdefault(inv["vendor"], []).append(inv)
    return index
