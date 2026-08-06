"""HITL and time-travel tests. InMemorySaver, no API key."""
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph.build import build_graph
from graph.context import LedgerContext
from graph.routers import MAX_REMATCH, route_after_investigate
from stubs.po_db import PurchaseOrderDB

INVOICE = str(sorted(Path("data/generated").glob("*.txt"))[0])


@pytest.fixture
def setup():
    graph = build_graph(checkpointer=InMemorySaver())
    ctx = LedgerContext(tenant_id="t", po_db=PurchaseOrderDB(),
                        variance_tolerance=0.0)      # force a hold
    return graph, ctx, {"configurable": {"thread_id": "t:INV-1"}}


def start(graph, ctx, config):
    return graph.invoke({"invoice_path": INVOICE}, context=ctx, config=config)


# ---- the pause ---------------------------------------------------------
def test_run_pauses_instead_of_finishing(setup):
    graph, ctx, config = setup
    result = start(graph, ctx, config)
    assert "__interrupt__" in result


def test_paused_thread_reports_what_it_is_waiting_for(setup):
    graph, ctx, config = setup
    start(graph, ctx, config)
    snap = graph.get_state(config)
    assert snap.next != ()                      # not finished
    payload = snap.tasks[0].interrupts[0].value
    assert "allowed_actions" in payload
    assert payload["invoice_id"]


def test_payload_excludes_raw_text(setup):
    """It holds bank details and gets streamed to a browser on Day 20."""
    graph, ctx, config = setup
    start(graph, ctx, config)
    payload = graph.get_state(config).tasks[0].interrupts[0].value
    assert "raw_text" not in payload


# ---- resume ------------------------------------------------------------
def test_approve_completes_the_thread(setup):
    graph, ctx, config = setup
    start(graph, ctx, config)
    out = graph.invoke(Command(resume={"action": "approve", "approver": "ops"}),
                       context=ctx, config=config)
    assert out["decision"] == "auto_approve"
    assert graph.get_state(config).next == ()


def test_reject_completes_with_a_reject(setup):
    graph, ctx, config = setup
    start(graph, ctx, config)
    out = graph.invoke(Command(resume={"action": "reject", "approver": "ops"}),
                       context=ctx, config=config)
    assert out["decision"] == "reject"


def test_resume_survives_a_new_graph_object(setup):
    """The proof that the pause is durable, not in-memory: same checkpointer,
    brand new compiled graph, as if a different process picked it up."""
    graph, ctx, config = setup
    start(graph, ctx, config)

    reborn = build_graph(checkpointer=graph.checkpointer)
    out = reborn.invoke(Command(resume={"action": "approve"}),
                        context=ctx, config=config)
    assert out["decision"] == "auto_approve"


# ---- edit --------------------------------------------------------------
def test_edit_reruns_the_policy_check(setup):
    """as_node='extract' is load-bearing: policy must see the human's number."""
    graph, ctx, config = setup
    start(graph, ctx, config)

    graph.update_state(config, {"total": 1.0}, as_node="extract")
    snap = graph.get_state(config)
    assert snap.values["total"] == 1.0
    assert "decide" in str(snap.next)            # policy is scheduled again


# ---- the back-edge -----------------------------------------------------
def test_router_sends_corrected_facts_back_to_policy():
    assert route_after_investigate(
        {"corrected_po_number": "PO-4002"}) == "decide"


def test_router_goes_to_the_gate_when_nothing_was_corrected():
    assert route_after_investigate(
        {"verdict": {"root_cause": "price variance"}}) == "approval_gate"


def test_rematch_is_bounded():
    """Otherwise an investigator that keeps producing PO numbers loops."""
    assert route_after_investigate(
        {"corrected_po_number": "PO-1", "rematch_attempts": MAX_REMATCH}
    ) == "approval_gate"


def test_router_never_reads_the_recommendation():
    """THE guard. Routing on the model's opinion lets an injection skip human
    review - Day 24's claim depends on this never happening.

    Note that a signature check is not enough here: the router takes the whole
    state either way. Inspect the source."""
    import inspect
    src = inspect.getsource(route_after_investigate)
    body = src.split('"""')[-1]              # ignore the docstring's warning
    for forbidden in ("recommendation", "confidence", "root_cause", "verdict"):
        assert forbidden not in body, f"router reads model output: {forbidden}"


def test_an_approve_recommendation_cannot_skip_the_gate():
    """Behavioural twin of the source check - and NOT a substitute for it.

    Verified: with an unsafe router that reads the recommendation only on the
    corrected-facts branch, THIS test still passes (it never sets
    corrected_po_number) while the source check above fails. Behavioural tests
    can only probe states you thought to construct; the source check covers the
    branch you did not.
    """
    assert route_after_investigate({
        "verdict": {"recommendation": "approve", "confidence": 0.99},
    }) == "approval_gate"


# ---- time travel -------------------------------------------------------
def test_forking_from_a_past_checkpoint_leaves_the_original(setup):
    graph, ctx, config = setup
    start(graph, ctx, config)
    before = len(list(graph.get_state_history(config)))

    target = next(s.config for s in graph.get_state_history(config)
                  if s.next == ("decide",))
    lenient = LedgerContext(tenant_id="t", po_db=PurchaseOrderDB(),
                            variance_tolerance=0.9)
    graph.invoke(None, context=lenient, config=target)

    assert len(list(graph.get_state_history(config))) > before
