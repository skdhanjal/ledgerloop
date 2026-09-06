from typing import TypedDict


class InvoiceState(TypedDict, total=False):
    """Minimal Day 2 shape: enough fields to prove the node/partial-update
    contract. Day 3 replaces this with the full state + reducers."""

    invoice_id: str
    tenant_id: str
    raw_text: str
    fields: dict
    decision: str
    audit: list[str]
