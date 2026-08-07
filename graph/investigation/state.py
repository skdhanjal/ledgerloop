"""The investigation subgraph's OWN state.

Deliberately not InvoiceState. This graph does not know what an invoice_path
is, what posting means, or that a checkpointer exists. It knows: here is an
exception, here are some tools, produce a verdict.

That ignorance is the point - it is what lets the investigator change on
Days 15-17 without touching the payment pipeline.
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from ..extraction import ExceptionVerdict          # shared vocabulary, not state

class InvestigationState(TypedDict, total=False):
    # --- input (written by the wrapper) ---
    exception_codes: list[str]
    vendor: str
    po_number: str | None
    total: float
    prior_knowledge: list[str]

    # --- internal ---
    messages: Annotated[list, add_messages]
    tool_calls_made: int

    # --- output (read by the wrapper) ---
    verdict: dict | None
