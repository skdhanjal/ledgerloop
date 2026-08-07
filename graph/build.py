"""Assemble the graph with a context schema and a public contract."""
from typing import Literal
from langgraph.graph import END, START, StateGraph

from config import get_model
from graph.approval import approval_gate, needs_human
from graph.extract_node import make_extract
from graph.fanout import fan_out_lines, reconcile
from graph.matching import match_line

from .context import LedgerContext
from .nodes import decide, extract, intake, post, escalate, investigate
from .schemas import DecisionResult, InvoiceRequest
from .state import InvoiceState
from .routers import route_after_approval_gate, route_after_decide, MAX_EXTRACT_ATTEMPTS, route_after_extract, route_after_investigate
from .tools import build_invoice_index, make_tools

from .investigation.graph import build_investigation_graph
from .investigation.wrapper import make_investigate_node

# The loop body is one node (extract), so each retry costs one super-step.
# Straight-line path is ~5 steps. Give the hard brake headroom over the
# semantic one, so the DESIGNED exit fires first and the safety net never does.
RECURSION_LIMIT = MAX_EXTRACT_ATTEMPTS * 2 + 8

Impl = Literal["handbuilt", "harness"]

def build_graph(
        model=None, 
        po_db=None, 
        checkpointer = None, 
        store= None, 
        tolerance=0.05
    ):
    """model and po_db are injectable so tests can pass fakes (Day 4's payoff)."""
    from stubs.po_db import PurchaseOrderDB

    model = model or get_model()
    po_db = po_db or PurchaseOrderDB()
    tools = make_tools(po_db, build_invoice_index())
    investigation = build_investigation_graph(model, tools)

    builder = StateGraph(
        InvoiceState,                    # internal working state
        context_schema=LedgerContext,    # per-run dependencies
        input_schema=InvoiceRequest,     # what callers may send
        output_schema=DecisionResult,    # what callers receive
    )

    builder.add_node("intake", intake)
    builder.add_node("extract", make_extract(model))
    builder.add_node("match_line", match_line)
    builder.add_node("reconcile", reconcile, defer=True)
    builder.add_node("decide", decide)
    builder.add_node("investigate", make_investigate_node(investigation))
    builder.add_node("escalate", escalate)
    builder.add_node("post", post)
    builder.add_node("approval_gate", approval_gate)


    builder.add_edge(START, "intake")
    builder.add_edge("intake", "extract")

    # extract -> either retry/escalate, or fan out one worker per line
    def after_extract(state: InvoiceState):
        if not state.get("extract_ok"):
             return route_after_extract(state)

        return fan_out_lines(state, po_db, tolerance)

    builder.add_conditional_edges("extract", after_extract, ["extract", "escalate", "match_line"])

    builder.add_edge("match_line", "reconcile")
    builder.add_edge("reconcile", "decide")

    builder.add_conditional_edges("decide", route_after_decide, {
        "post": "post",
        "investigate": "investigate"
    })

    builder.add_edge("investigate", "approval_gate")

    builder.add_conditional_edges("approval_gate", route_after_approval_gate, {
        "post": "post",
        "reject": END
    })

    builder.add_edge("post", END)
    builder.add_edge("escalate", END)

    return builder.compile(checkpointer=checkpointer, store=store)


graph = build_graph()
