"""Graph state. Kept deliberately thin today - reducers arrive on Day 3."""
from typing import TypedDict, Literal

class InvoiceState(TypedDict, total=False):
    """State for one invoice moving through the graph.

    total=False means every key is optional at runtime. That matches reality:
    a node early in the graph has not yet written the keys later nodes produce.
    """
    # set by the caller
    invoice_path: str

    # written by intake
    raw_text: str
    invoice_id: str

    # written by extract   (hardcoded today, real on Day 8)
    vendor: str
    invoice_no: str
    po_number: str
    total: float

    # written by decide    (hardcoded today, real on Day 5)
    decision: Literal["auto_approve", "hold", "reject"]
    reason: str

    # written by post      (hardcoded today, real on Day 19)
    posted: bool
