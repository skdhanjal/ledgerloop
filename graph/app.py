"""Module-level export for the runtime.

The runtime IMPORTS this at build time, before your environment is fully
configured - so construction here must be cheap and side-effect free.

Do NOT open a Postgres connection, download a model, or read a secret at
import. The platform supplies the checkpointer and store; a local run uses
build_app() instead.
"""

from config import get_model
from graph.build import build_graph
from graph.checkpointing import get_checkpointer
from graph.context import LedgerContext
from graph.erp import get_erp_client
from graph.store import get_store
from stubs.po_db import PurchaseOrderDB
from langgraph.cache.sqlite import SqliteCache
from graph.investigation.graph import build_investigation_graph

def build_app(*, 
        checkpointer=None, 
        store_kind="postgres", 
        model=None,
        cache: bool = False, 
        router_model=None, 
        tolerance=0.05,
        tiering: bool = True
    ):
    """The single place that knows how LedgerLoop is wired.

    Tests override every argument; run scripts and the CLI call it with none.
    """
    router = router_model or get_model("local" if tiering else "strong")

    graph_cache = None

    if cache:
        graph_cache = SqliteCache(path=".cache/ledgerloop.sqlite")

    return build_graph(
        model=model or get_model(),
        router_model=router,
        po_db=PurchaseOrderDB(),
        checkpointer= checkpointer,
        store=get_store(store_kind),
        tolerance=tolerance,
        cache=graph_cache,
        dev=cache, 
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


def _graph():
    """Assembled without a checkpointer or store - the runtime injects both."""

    model = get_model("strong")

    return build_graph(
        model=model,
        po_db=PurchaseOrderDB(),      # reads a committed JSON file, no network
        checkpointer=None,            # <- supplied by the platform
        store=None,                   # <- supplied by the platform
    )

graph = _graph()          # the variable langgraph.json points a
