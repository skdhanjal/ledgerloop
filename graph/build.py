"""Assemble the graph with a context schema and a public contract."""
from langgraph.graph import END, START, StateGraph

from .context import LedgerContext
from .nodes import decide, extract, intake, post, escalate, investigate
from .schemas import DecisionResult, InvoiceRequest
from .state import InvoiceState
from .routers import route_after_decide, MAX_EXTRACT_ATTEMPTS, route_after_extract

# The loop body is one node (extract), so each retry costs one super-step.
# Straight-line path is ~5 steps. Give the hard brake headroom over the
# semantic one, so the DESIGNED exit fires first and the safety net never does.
RECURSION_LIMIT = MAX_EXTRACT_ATTEMPTS * 2 + 8

def build_graph():
    builder = StateGraph(
        InvoiceState,                    # internal working state
        context_schema=LedgerContext,    # per-run dependencies
        input_schema=InvoiceRequest,     # what callers may send
        output_schema=DecisionResult,    # what callers receive
    )

    for name, fn in [("intake", intake), ("extract", extract), ("decide", decide),
                     ("investigate", investigate), ("escalate", escalate), ("post", post)]:
        builder.add_node(name, fn)

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

    return builder.compile()


graph = build_graph()
