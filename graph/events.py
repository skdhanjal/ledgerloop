from typing import Literal
from pydantic import BaseModel

class ProgressEvent(BaseModel):
    type: Literal["progress"] = "progress"
    stage: Literal["intake", "extract", "match", "reconcile", "decide", "investigate", "post"]
    label: str
    done: int = 0
    total: int = 0

    # Set by the SERVER from the checkpoint namespace, never by a node.
    # depth 0 = the top-level graph, 1 = a subgraph, 2 = a subgraph of one.
    depth: int = 0
    # The node that owns the subgraph ("investigate"), NOT the raw namespace.
    # A namespace is "investigate:8f2c-4d1a" - the UUID is an internal id and
    # has no business in a browser.
    source: str | None = None

class DecisionEvent(BaseModel):
    type: Literal["decision"] = "decision"
    decision: Literal["auto_approve", "hold", "reject"]
    reason: str


class ApprovalEvent(BaseModel):
    """Emitted when the graph pauses. This IS the UI contract from Day 11."""
    type: Literal["approval_required"] = "approval_required"
    thread_id: str
    payload: dict                 # exactly what interrupt() carried