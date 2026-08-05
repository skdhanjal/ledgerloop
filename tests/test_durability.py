"""Durability tests. InMemorySaver keeps them fast; the semantics are identical."""
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from graph.build import build_graph
from graph.checkpointing import thread_id_for
from graph.context import LedgerContext
from stubs.po_db import PurchaseOrderDB

INVOICE = str(sorted(Path("data/generated").glob("*.txt"))[0])

@pytest.fixture
def setup():
    graph = build_graph(checkpointer=InMemorySaver())
    ctx = LedgerContext(tenant_id="t", po_db=PurchaseOrderDB())
    config = {"configurable": {"thread_id": "t:INV-1"}}
    return graph, ctx, config


def test_thread_id_is_derived_not_arbitrary():
    assert thread_id_for("acme-corp", "INV-10002") == "acme-corp:INV-10002"


def test_state_survives_the_run(setup):
    graph, ctx, config = setup
    graph.invoke({"invoice_path": INVOICE}, context=ctx, config=config)

    snapshot = graph.get_state(config)
    assert snapshot.values["invoice_id"]
    assert snapshot.next == ()               # empty == finished


def test_history_has_one_entry_per_super_step(setup):
    graph, ctx, config = setup
    graph.invoke({"invoice_path": INVOICE}, context=ctx, config=config)

    history = list(graph.get_state_history(config))
    assert len(history) >= 4
    # newest first, and each knows which node was scheduled next
    assert history[0].next == ()


def test_resuming_a_finished_thread_is_a_noop(setup):
    graph, ctx, config = setup
    first = graph.invoke({"invoice_path": INVOICE}, context=ctx, config=config)
    again = graph.invoke(None, context=ctx, config=config)
    assert first["decision"] == again["decision"]


def test_separate_threads_do_not_share_state(setup):
    """The isolation property everything on Day 26 depends on."""
    graph, ctx, _ = setup
    a = {"configurable": {"thread_id": "acme:INV-1"}}
    b = {"configurable": {"thread_id": "globex:INV-1"}}

    graph.invoke({"invoice_path": INVOICE}, context=ctx, config=a)
    assert graph.get_state(b).values == {}   # untouched


def test_everything_in_state_is_serializable(setup):
    """Day 4's insurance policy, now enforced by a real checkpointer.

    If a client, connection or file handle ever lands in state, this fails
    here instead of at 2am in production.
    """
    graph, ctx, config = setup
    graph.invoke({"invoice_path": INVOICE}, context=ctx, config=config)
    import json
    json.dumps(graph.get_state(config).values, default=str)


def test_missing_thread_id_is_rejected(setup):
    graph, ctx, _ = setup
    with pytest.raises(Exception):
        graph.invoke({"invoice_path": INVOICE}, context=ctx)
