"""Prove the loop terminates - with a mocked extractor that ALWAYS fails.

This is the test people skip and then discover in production. It runs in
milliseconds and it is the only proof that your brakes actually work.
"""
from pathlib import Path

from langgraph.errors import GraphRecursionError

from graph.build import RECURSION_LIMIT, build_graph
from graph.context import LedgerContext
from stubs.po_db import PurchaseOrderDB

INVOICE = str(sorted(Path("data/generated").glob("*.txt"))[0])

def ctx():
    return LedgerContext(tenant_id="t", po_db=PurchaseOrderDB())


def test_always_failing_extraction_escalates_rather_than_hanging(monkeypatch):
    import graph.nodes as nodes

    def broken(state):
        return {"extract_attempts": state.get("extract_attempts", 0) + 1,
                "extract_ok": False}

    monkeypatch.setattr(nodes, "extract", broken)
    g = build_graph()

    result = g.invoke({"invoice_path": INVOICE}, context=ctx(),
                      config={"recursion_limit": RECURSION_LIMIT})

    # the SEMANTIC brake fired: a real decision, not an exception
    assert result["decision"] == "hold"
    assert result["reason"] == "escalated_extraction_failed"


def test_hard_brake_exists_if_the_semantic_one_is_removed(monkeypatch):
    """Sanity: with no attempt cap, recursion_limit still stops the run."""
    import graph.routers as routers
    monkeypatch.setattr(routers, "MAX_EXTRACT_ATTEMPTS", 10_000)

    import graph.nodes as nodes
    monkeypatch.setattr(nodes, "extract",
                        lambda s: {"extract_attempts": s.get("extract_attempts", 0) + 1,
                                   "extract_ok": False})

    g = build_graph()
    try:
        g.invoke({"invoice_path": INVOICE}, context=ctx(),
                 config={"recursion_limit": 8})
        raise AssertionError("expected GraphRecursionError")
    except GraphRecursionError:
        pass
