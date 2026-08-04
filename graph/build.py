"""Assemble the graph with a context schema and a public contract."""
from langgraph.graph import END, START, StateGraph

from .context import LedgerContext
from .nodes import decide, extract, intake, post
from .schemas import DecisionResult, InvoiceRequest
from .state import InvoiceState


def build_graph():
    builder = StateGraph(
        InvoiceState,                    # internal working state
        context_schema=LedgerContext,    # per-run dependencies
        input_schema=InvoiceRequest,     # what callers may send
        output_schema=DecisionResult,    # what callers receive
    )

    builder.add_node("intake", intake)
    builder.add_node("extract", extract)
    builder.add_node("decide", decide)
    builder.add_node("post", post)

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "extract")
    builder.add_edge("extract", "decide")
    builder.add_edge("decide", "post")
    builder.add_edge("post", END)

    return builder.compile()


graph = build_graph()
