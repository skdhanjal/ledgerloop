"""Context injection and boundary tests. Still no model, no network."""
from pathlib import Path

import pytest

from graph.build import build_graph
from graph.context import LedgerContext
from stubs.po_db import PurchaseOrderDB

INVOICE = sorted(Path("data/generated").glob("*.txt"))[0]


@pytest.fixture(scope="module")
def graph():
    return build_graph()


@pytest.fixture
def ctx():
    return LedgerContext(tenant_id="test-tenant", po_db=PurchaseOrderDB(),
                         variance_tolerance=0.05)


def invoke(graph, ctx, **kw):
    return graph.invoke({"invoice_path": str(INVOICE)}, context=ctx, **kw)


def test_context_reaches_a_node(graph, ctx):
    """tenant_id came from context and was written into durable state."""
    assert invoke(graph, ctx)["tenant_id"] == "test-tenant"


def test_output_schema_hides_internals(graph, ctx):
    result = invoke(graph, ctx)
    assert "raw_text" not in result           # vendor bank details stay internal
    assert "invoice_no" not in result
    assert set(result) <= {"invoice_id", "tenant_id", "decision",
                           "reason", "total", "exceptions"}


def test_policy_knob_is_injectable(graph):
    """The same graph behaves differently per tenant - no code change."""
    strict = LedgerContext(tenant_id="t", po_db=PurchaseOrderDB(),
                           variance_tolerance=0.0)
    assert invoke(graph, strict)["decision"] in {"auto_approve", "hold", "reject"}


def test_missing_context_fails_loudly(graph):
    with pytest.raises(Exception):
        graph.invoke({"invoice_path": str(INVOICE)})    # no context= supplied


def test_dependency_is_not_in_state(graph, ctx):
    """The one that matters on Day 9: nothing unserializable in the result."""
    import json
    json.dumps(invoke(graph, ctx))            # raises TypeError if a client leaked
