"""Structural tests. No API key, no network, ~40ms - this is what CI runs (Day 23)."""

from pathlib import Path
import pytest

from graph.build import build_graph

INVOICE = sorted(Path("data/generated").glob("*.txt"))[0]

@pytest.fixture(scope="module")
def graph():
    return build_graph()


def test_graph_has_expected_nodes(graph):
    names = set(graph.get_graph().nodes)
    assert {"intake", "extract", "decide", "post"} <= names


def test_invoke_returns_full_merged_state(graph):
    final = graph.invoke({"invoice_path": str(INVOICE)})
    # every node's delta is present in one dict
    assert final["invoice_id"]          # from intake
    assert final["vendor"]              # from extract
    assert final["decision"] == "hold"  # from decide
    assert final["posted"] is True      # from post


def test_input_key_survives_to_the_end(graph):
    final = graph.invoke({"invoice_path": str(INVOICE)})
    assert final["invoice_path"] == str(INVOICE)


def test_missing_file_fails_loudly(graph):
    with pytest.raises(FileNotFoundError):
        graph.invoke({"invoice_path": "data/generated/does-not-exist.txt"})
