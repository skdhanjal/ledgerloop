"""Assemble and compile the graph."""
from langgraph.graph import StateGraph, START, END

from .nodes import intake, extract, decide, post
from .state import InvoiceState

def build_graph():
    builder = StateGraph(InvoiceState)

    # names are durable identifiers - they show up in checkpoints and traces
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


graph = build_graph()          # module-level so `langgraph dev` can find it (Day 25)
