"""Assemble the graph with a context schema and a public contract."""
from typing import Literal
from langgraph.graph import END, START, StateGraph

from config import get_model
from graph.extract_node import make_extract
from graph.investigator import investigate_node_factory
from graph.investigator_v2 import investigate_node_factory_v2
from graph.investigator_v3 import investigate_node_factory_v3

from .context import LedgerContext
from .nodes import decide, extract, intake, post, escalate, investigate
from .schemas import DecisionResult, InvoiceRequest
from .state import InvoiceState
from .routers import route_after_decide, MAX_EXTRACT_ATTEMPTS, route_after_extract
from .tools import build_invoice_index, make_tools

# The loop body is one node (extract), so each retry costs one super-step.
# Straight-line path is ~5 steps. Give the hard brake headroom over the
# semantic one, so the DESIGNED exit fires first and the safety net never does.
RECURSION_LIMIT = MAX_EXTRACT_ATTEMPTS * 2 + 8

Impl = Literal["handbuilt", "harness"]

def build_graph(model=None, po_db=None, investigator: Impl = "harness", checkpointer = None):
    """model and po_db are injectable so tests can pass fakes (Day 4's payoff)."""
    from stubs.po_db import PurchaseOrderDB

    model = model or get_model()
    po_db = po_db or PurchaseOrderDB()
    tools = make_tools(po_db, build_invoice_index())
    factory = (investigate_node_factory if investigator == "handbuilt" else investigate_node_factory_v3)

    builder = StateGraph(
        InvoiceState,                    # internal working state
        context_schema=LedgerContext,    # per-run dependencies
        input_schema=InvoiceRequest,     # what callers may send
        output_schema=DecisionResult,    # what callers receive
    )

    builder.add_node("intake", intake)
    builder.add_node("extract", make_extract(model))
    builder.add_node("decide", decide)
    builder.add_node("investigate", factory(model, tools))
    builder.add_node("escalate", escalate)
    builder.add_node("post", post)

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "extract")

    # retry loop: extract -> extract (backward edge) until ok or attempts spent
    builder.add_conditional_edges("extract", route_after_extract, {
        "extract": "extract",
        "decide": "decide",
        "escalate": "escalate"
    })

    builder.add_conditional_edges("decide", route_after_decide, {
        "post": "post",
        "investigate": "investigate"
    })

    builder.add_edge("post", END)
    builder.add_edge("escalate", END)
    builder.add_edge("investigate", END)

    return builder.compile(checkpointer=checkpointer)


graph = build_graph()
