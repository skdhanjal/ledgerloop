from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from ledgerloop.graph.state import (
    DecisionResult,
    InvoiceFields,
    InvoiceRequest,
    InvoiceState,
    LedgerContext,
)


def intake(state: InvoiceState, runtime: Runtime[LedgerContext]) -> dict:
    """Hardcoded Day 2/3 stand-in: no LLM, no parsing, just a partial
    update. Reads `runtime.context.tenant_id` -- distinct from, but equal
    to, `state["tenant_id"]` -- to prove context injection actually
    happens (Day 3's concept note on state vs. context lifetimes)."""
    return {
        "audit": [
            {
                "node": "intake",
                "message": f"received raw_text for tenant={runtime.context.tenant_id}",
            }
        ],
    }


def extract_fields(state: InvoiceState) -> dict:
    """Hardcoded Day 3 stand-in for the real extraction node (Day 8).
    Carries bank fields on purpose, so the output-schema test proves
    they never reach a caller."""
    fields = InvoiceFields(
        vendor="PLACEHOLDER",
        invoice_no="INV-000",
        total=0.0,
        bank_account="ACCT-HARDCODED",
        routing_number="ROUTING-HARDCODED",
    )
    return {
        "fields": fields,
        "audit": [{"node": "extract_fields", "message": "hardcoded fields"}],
    }


def decide_policy(state: InvoiceState) -> dict:
    """Hardcoded Day 3 stand-in for the real policy gate (Day 5)."""
    invoice_id = state.get("invoice_id", "")
    tenant_id = state.get("tenant_id", "")
    return {
        "decision": "auto_approve",
        "idempotency_key": f"{tenant_id}:{invoice_id}",
        "audit": [{"node": "decide_policy", "message": "hardcoded auto_approve"}],
    }


def post_to_erp(state: InvoiceState) -> dict:
    """Hardcoded Day 2/3 stand-in for the real idempotent posting node (Day 19)."""
    return {
        "audit": [
            {"node": "post_to_erp", "message": f"posted with decision={state.get('decision')}"}
        ],
    }


def build_graph():
    """Linear skeleton: intake -> extract_fields -> decide_policy -> post_to_erp.

    Day 3 adds the schema wiring around the same four nodes: `context_schema`
    injects non-serializable per-tenant dependencies via `runtime.context`;
    `input_schema` / `output_schema` narrow what a caller can send in and
    what they get back, independent of the full internal `InvoiceState`.
    """
    graph = StateGraph(
        InvoiceState,
        context_schema=LedgerContext,
        input_schema=InvoiceRequest,
        output_schema=DecisionResult,
    )
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
