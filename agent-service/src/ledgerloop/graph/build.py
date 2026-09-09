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
    return {
        "audit": [
            {
                "node": "intake",
                "message": f"received raw_text for tenant={runtime.context.tenant_id}",
            }
        ],
    }


def extract_fields(state: InvoiceState) -> dict:
    # Bank fields are hardcoded on purpose, to prove output_schema filters
    # them out of invoke()'s return value rather than nothing sensitive
    # ever being produced.
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
    invoice_id = state.get("invoice_id", "")
    tenant_id = state.get("tenant_id", "")
    return {
        "decision": "auto_approve",
        "idempotency_key": f"{tenant_id}:{invoice_id}",
        "audit": [{"node": "decide_policy", "message": "hardcoded auto_approve"}],
    }


def post_to_erp(state: InvoiceState) -> dict:
    return {
        "audit": [
            {"node": "post_to_erp", "message": f"posted with decision={state.get('decision')}"}
        ],
    }


def build_graph():
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
