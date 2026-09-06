from ledgerloop.graph import build_graph


def test_linear_traversal_and_partial_updates():
    graph = build_graph()
    result = graph.invoke({"invoice_id": "INV-TEST", "tenant_id": "acme", "raw_text": "hello"})

    # Each node's own contribution shows up, in the order it ran.
    assert result["audit"] == [
        "intake: received raw_text",
        "extract_fields: hardcoded fields",
        "decide_policy: hardcoded auto_approve",
        "post_to_erp: posted with decision=auto_approve",
    ]

    # Inputs a node never touched are preserved -- proof these are partial
    # updates merged over the running state, not full-state replacements.
    assert result["invoice_id"] == "INV-TEST"
    assert result["tenant_id"] == "acme"
    assert result["fields"] == {"vendor": "PLACEHOLDER", "total": 0}
    assert result["decision"] == "auto_approve"


def test_node_names_are_durable_identifiers():
    node_names = set(build_graph().get_graph().nodes) - {"__start__", "__end__"}
    assert node_names == {"intake", "extract_fields", "decide_policy", "post_to_erp"}
