"""Graph state, now with explicit merge rules per channel."""
import operator
from typing import Annotated, Literal, TypedDict

from graph.extraction import ExceptionVerdict

from .reducers import bounded_audit, dedupe_exceptions, merge_line_matches

class InvoiceState(TypedDict, total=False):
    # ---- single-writer channels: default overwrite ----------------------
    # If two nodes ever write these in one super-step, LangGraph raises
    # InvalidUpdateError. That crash is intentional - it means a wiring bug.
    invoice_path: str
    raw_text: str
    invoice_id: str
    tenant_id: str
    vendor: str
    invoice_no: str
    po_number: str
    total: float
    subtotal: float
    decision: Literal["auto_approve", "hold", "reject"]
    reason: str
    posted: bool
    extract_ok: bool
    extract_attempts: int
    investigation: str
    verdict: dict

    # ---- multi-writer channels: reducers required ------------------------
    # Day 14 fans out one matcher per line item; all land in one super-step.
    line_matches: Annotated[list[dict], merge_line_matches]

    # Any node may raise an exception flag; we want one per code, most severe.
    exceptions: Annotated[list[dict], dedupe_exceptions]

    # Append-only, capped. Every routing decision lands here (Day 15).
    audit: Annotated[list[dict], bounded_audit]

    # Plain accumulation - used by the Day 6 investigator's scratch notes.
    notes: Annotated[list[str], operator.add]
