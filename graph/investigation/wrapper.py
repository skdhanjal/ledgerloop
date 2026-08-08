"""The transform layer: the ONE place the two schemas meet.

Both functions are pure and take no graph, so they are tested directly. When
someone changes the investigation schema, a transform test fails here rather
than a verdict going wrong in production.
"""
from langgraph.runtime import Runtime

from ..context import LedgerContext
from ..memory import recall_vendor
from ..state import InvoiceState
from .state import InvestigationState


def to_investigation(state: InvoiceState,
                     prior_knowledge: list[str]) -> InvestigationState:
    """Parent -> child. Note what is NOT passed: raw_text, invoice_path,
    audit, the whole message history. The investigator gets facts, not a
    dump of everything we happen to have."""
    return {
        "exception_codes": [e["code"] for e in state.get("exceptions", [])],
        "vendor": state.get("vendor", ""),
        "po_number": state.get("po_number"),
        "invoice_no": state.get("invoice_no"),
        "total": state.get("total", 0.0),
        "prior_knowledge": prior_knowledge,
        "messages": [],
        "tool_calls_made": 0,
    }


def from_investigation(result: InvestigationState) -> dict:
    """Child -> parent. Only the parent's channels, never the child's internals.

    The message history in particular stays in the child: it is 8 KB that the
    payment pipeline has no use for, and copying it up would double the
    checkpoint cost for nothing (Day 9's measurement).
    """
    verdict = result.get("verdict")
    if verdict is None:
        return {
            "investigation": "investigator produced no verdict",
            "exceptions": [{"code": "investigation_failed", "severity": "medium",
                            "detail": "no structured verdict"}],
            "audit": [{"node": "investigate", "event": "no_verdict"}],
        }
    return {
        "verdict": verdict,
        "investigation": verdict["root_cause"],
        "notes": [f"confidence {verdict['confidence']:.2f}"],
        "audit": [{"node": "investigate", "event": "verdict",
                   "recommendation": verdict["recommendation"],
                   "confidence": verdict["confidence"],
                   "tool_calls": result.get("tool_calls_made", 0)}],
    }


def make_investigate_node(investigation_graph):
    """Mount the subgraph behind the transforms."""

    def investigate(state: InvoiceState, runtime: Runtime[LedgerContext]) -> dict:
        prior = [m["text"] for m in recall_vendor(
            runtime.store, runtime.context.tenant_id,
            state.get("vendor", ""), query=state.get("reason", ""), limit=3)]

        result = investigation_graph.invoke(to_investigation(state, prior))
        return from_investigation(result)

    return investigate
