from langgraph.graph import END, START, StateGraph

from ledgerloop.graph.state import InvoiceState


def intake(state: InvoiceState) -> dict:
    """Hardcoded Day 2 stand-in: no LLM, no parsing, just a partial update."""
    audit = state.get("audit", [])
    return {"audit": [*audit, "intake: received raw_text"]}


def extract_fields(state: InvoiceState) -> dict:
    """Hardcoded Day 2 stand-in for the real extraction node (Day 8)."""
    audit = state.get("audit", [])
    fields = {"vendor": "PLACEHOLDER", "total": 0}
    return {"fields": fields, "audit": [*audit, "extract_fields: hardcoded fields"]}


def decide_policy(state: InvoiceState) -> dict:
    """Hardcoded Day 2 stand-in for the real policy gate (Day 5)."""
    audit = state.get("audit", [])
    return {"decision": "auto_approve", "audit": [*audit, "decide_policy: hardcoded auto_approve"]}


def post_to_erp(state: InvoiceState) -> dict:
    """Hardcoded Day 2 stand-in for the real idempotent posting node (Day 19)."""
    audit = state.get("audit", [])
    return {"audit": [*audit, f"post_to_erp: posted with decision={state.get('decision')}"]}


def build_graph():
    """Linear skeleton: intake -> extract_fields -> decide_policy -> post_to_erp.

    Node names are durable identifiers (they'll appear in checkpoints, traces
    and interrupt config from Day 9 onward) and are chosen to match the names
    Days 5/8/19 formalize, so no node gets renamed later.
    """
    graph = StateGraph(InvoiceState)
    graph.add_node("intake", intake)
    graph.add_node("extract_fields", extract_fields)
    graph.add_node("decide_policy", decide_policy)
    graph.add_node("post_to_erp", post_to_erp)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "extract_fields")
    graph.add_edge("extract_fields", "decide_policy")
    graph.add_edge("decide_policy", "post_to_erp")
    graph.add_edge("post_to_erp", END)

    return graph.compile()
