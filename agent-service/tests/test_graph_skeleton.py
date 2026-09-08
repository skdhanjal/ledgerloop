from ledgerloop.graph import build_graph
from ledgerloop.graph.state import LedgerContext


def _invoke(invoice_id="INV-TEST", tenant_id="acme"):
    graph = build_graph()
    return graph.invoke(
        {"invoice_id": invoice_id, "tenant_id": tenant_id, "raw_text": "hello"},
        context=LedgerContext(tenant_id=tenant_id),
    )


def test_linear_traversal_and_partial_updates():
    result = _invoke()

    # Each node's own contribution shows up, in the order it ran.
    assert [entry["node"] for entry in result["audit"]] == [
        "intake",
        "extract_fields",
        "decide_policy",
        "post_to_erp",
    ]

    # Inputs a node never touched are preserved -- proof these are partial
    # updates merged over the running state, not full-state replacements.
    assert result["invoice_id"] == "INV-TEST"
    assert result["tenant_id"] == "acme"
    assert result["decision"] == "auto_approve"
    assert result["idempotency_key"] == "acme:INV-TEST"


def test_node_names_are_durable_identifiers():
    node_names = set(build_graph().get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"intake", "extract_fields", "decide_policy", "post_to_erp"}


def test_output_schema_hides_raw_text_and_bank_fields():
    result = _invoke()

    # output_schema (DecisionResult) narrows invoke()'s return value --
    # raw_text and fields (which carries bank_account/routing_number)
    # never leave the graph, with no node having to remember to redact them.
    assert "raw_text" not in result
    assert "fields" not in result
    assert "bank_account" not in result
    assert "routing_number" not in result
