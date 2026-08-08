"""Assemble the whole application. Everything before this file is parts."""
from config import get_model
from graph.build import build_graph
from graph.checkpointing import get_checkpointer
from graph.context import LedgerContext
from graph.erp import get_erp_client
from graph.store import get_store
from stubs.po_db import PurchaseOrderDB


def build_app(*, checkpointer=None, checkpointer_kind="postgres", store_kind="postgres", model=None):
    """The single place that knows how LedgerLoop is wired.

    Tests override every argument; run scripts and the CLI call it with none.
    """
    return build_graph(
        model=model or get_model(),
        po_db=PurchaseOrderDB(),
        checkpointer= checkpointer,
        store=get_store(store_kind)
    )


def context_for(tenant_id: str, **overrides) -> LedgerContext:
    """Per-tenant policy in one place. On Day 25 each of these becomes a
    named 'assistant' a finance lead can adjust without a deploy."""
    defaults = {
        "acme-corp":  dict(variance_tolerance=0.05, max_auto_approve=50_000),
        "globex-ltd": dict(variance_tolerance=0.00, max_auto_approve=1_000),
    }
    cfg = {**defaults.get(tenant_id, dict(variance_tolerance=0.05,
                                          max_auto_approve=10_000)), **overrides}
    return LedgerContext(tenant_id=tenant_id, po_db=PurchaseOrderDB(), erp=get_erp_client() ,**cfg)