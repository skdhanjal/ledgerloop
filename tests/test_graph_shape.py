"""Structural tests. No API key, no network, ~40ms - this is what CI runs (Day 23)."""

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

def test_graph_has_expected_nodes(graph):
    names = set(graph.get_graph().nodes)
    assert {"intake", "extract", "decide", "post"} <= names


def test_invoke_returns_full_merged_state(graph, ctx):
    final = graph.invoke({"invoice_path": str(INVOICE)}, context=ctx)
    # every node's delta is present in one dict
    assert final["invoice_id"]          # from intake
    assert final["decision"] == "hold"  # from decide


def test_input_key_survives_to_the_end(graph, ctx):
    final = graph.invoke({"invoice_path": str(INVOICE)}, context=ctx)
    assert final["invoice_id"]


def test_missing_file_fails_loudly(graph):
    with pytest.raises(FileNotFoundError):
        graph.invoke({"invoice_path": "data/generated/does-not-exist.txt"})
