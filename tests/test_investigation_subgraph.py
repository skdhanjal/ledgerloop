"""Subgraph tests: the transforms, then the subgraph alone, then the mount."""
import pytest

from graph.investigation.state import InvestigationState
from graph.investigation.wrapper import from_investigation, to_investigation

PARENT = {
    "invoice_path": "/data/x.txt",
    "raw_text": "INVOICE ... account 123456789012 ...",
    "invoice_id": "acme_004",
    "vendor": "Halvorsen Metals GmbH",
    "po_number": "PO-4002",
    "total": 4062.15,
    "exceptions": [{"code": "price_variance", "severity": "high", "detail": "35%"}],
    "audit": [{"node": "decide"}],
}

VERDICT = {"root_cause": "billed 114.75 vs PO 85.00", "evidence": ["lookup_po"],
           "recommendation": "hold", "confidence": 0.88}


# ---- transforms: pure functions, no graph -----------------------------
def test_child_receives_only_facts_it_needs():
    child = to_investigation(PARENT, prior_knowledge=[])
    assert child["exception_codes"] == ["price_variance"]
    assert child["vendor"] == "Halvorsen Metals GmbH"


def test_raw_text_never_crosses_the_boundary():
    """It holds bank details and the investigator has no use for it."""
    child = to_investigation(PARENT, prior_knowledge=[])
    assert "raw_text" not in child
    assert "invoice_path" not in child


def test_prior_knowledge_is_passed_through():
    child = to_investigation(PARENT, prior_knowledge=["bills in CASES of 12"])
    assert "CASES" in child["prior_knowledge"][0]


def test_output_maps_to_parent_channels_only():
    out = from_investigation({"verdict": VERDICT, "tool_calls_made": 3})
    assert out["verdict"] == VERDICT
    assert out["investigation"] == VERDICT["root_cause"]
    assert "messages" not in out          # 8 KB stays in the child


def test_missing_verdict_degrades_rather_than_raising():
    out = from_investigation({"verdict": None})
    assert out["exceptions"][0]["code"] == "investigation_failed"


def test_tool_call_count_reaches_the_audit_trail():
    out = from_investigation({"verdict": VERDICT, "tool_calls_made": 3})
    assert out["audit"][0]["tool_calls"] == 3


# ---- the subgraph in isolation ----------------------------------------
class FakeAgentGraph:
    """Stands in for the compiled investigation graph."""

    def __init__(self, verdict):
        self.verdict = verdict
        self.seen = None

    def invoke(self, state):
        self.seen = state
        return {"verdict": self.verdict, "tool_calls_made": 2, "messages": []}


def test_subgraph_can_be_exercised_without_the_parent():
    """The payoff: no invoice, no checkpointer, no policy engine needed."""
    fake = FakeAgentGraph(VERDICT)
    child_in: InvestigationState = to_investigation(PARENT, prior_knowledge=[])
    out = from_investigation(fake.invoke(child_in))
    assert out["investigation"] == VERDICT["root_cause"]
    assert fake.seen["po_number"] == "PO-4002"
