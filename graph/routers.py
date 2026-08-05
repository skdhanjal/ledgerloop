"""Routers: pure functions of state that name the next node.

Cheap and side-effect free, because LangGraph may re-execute them.
"""

from typing import Literal
from .state import InvoiceState

MAX_EXTRACT_ATTEMPTS = 2

def route_after_extract(state: InvoiceState) -> Literal["decide", "extract", "escalate"]:
    """Retry loop with both brakes visible in one place."""
    # print("extract_ok", state.get("extract_ok"))
    if state.get("extract_ok"):
        return "decide"

    attempts = state.get("extract_attempts", 0)

    if attempts >= MAX_EXTRACT_ATTEMPTS:
        return "escalate"
                # designed exit, not a crash
    # print("Goto-> extract")            
    return "extract"               # the backward edge

def route_after_decide(state: InvoiceState) -> Literal["post", "investigate"]:
    """auto_approve pays; anything else needs a look first."""
    return "post" if state.get("decision") == "auto_approve" else "investigate"