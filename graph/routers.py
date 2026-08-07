"""Routers: pure functions of state that name the next node.

Cheap and side-effect free, because LangGraph may re-execute them.
"""

from typing import Literal

from graph.approval import needs_human
from .state import InvoiceState

MAX_EXTRACT_ATTEMPTS = 2
MAX_REMATCH = 1 

def route_after_extract(state: InvoiceState) -> Literal["decide", "extract", "escalate"]:
    """Retry loop with both brakes visible in one place."""

    attempts = state.get("extract_attempts", 0)

    if attempts >= MAX_EXTRACT_ATTEMPTS:
        return "escalate"
                # designed exit, not a crash
                
    return "extract"               # the backward edge

def route_after_decide(state: InvoiceState) -> Literal["post", "investigate"]:
    """auto_approve pays; anything else needs a look first."""
    return "post" if state.get("decision") == "auto_approve" else "investigate"

def route_after_investigate(state: InvoiceState) -> Literal["post", "approval_gate"]:
    return "approval_gate" if needs_human(state) else "post"

def route_after_approval_gate(state: InvoiceState) -> Literal["post", "done"]:
    return "post" if state.get("decision") == "auto_Approve" else "reject"    