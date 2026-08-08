from typing import Literal
from pydantic import BaseModel


class ProgressEvent(BaseModel):
    """The ONLY thing the browser receives. Adding a field here is a
    deliberate API change; adding one to InvoiceState is not."""
    type: Literal["progress"] = "progress"
    stage: Literal["intake", "extract", "match", "reconcile",
                   "decide", "investigate", "post"]
    label: str                    # human text: "matching line 7 of 30"
    done: int = 0
    total: int = 0


class DecisionEvent(BaseModel):
    type: Literal["decision"] = "decision"
    decision: Literal["auto_approve", "hold", "reject"]
    reason: str


class ApprovalEvent(BaseModel):
    """Emitted when the graph pauses. This IS the UI contract from Day 11."""
    type: Literal["approval_required"] = "approval_required"
    thread_id: str
    payload: dict                 # exactly what interrupt() carried