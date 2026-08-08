"""Per-run dependencies. Never serialized, never in state, re-supplied every run."""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from graph.erp import ErpClient

if TYPE_CHECKING:                       # avoid an import cycle at runtime
    from stubs.po_db import PurchaseOrderDB


@dataclass
class LedgerContext:
    """Everything a run needs that is NOT a fact the run produced.

    Rule of thumb: if a resumed thread should get this value back from disk,
    it belongs in state. If the caller should supply it fresh, it belongs here.
    """
    tenant_id: str
    po_db: "PurchaseOrderDB"
    erp: ErpClient  

    # policy knobs - these are exactly what a finance lead will want to tune
    # per client without a deploy, which is why they are context and not
    # constants. On Day 25 each becomes an "assistant" configuration.
    variance_tolerance: float = 0.05        # 5% price variance auto-approves
    max_auto_approve: float = 50_000.0      # anything above always sees a human

    # model id comes from config.py, but lives here so a node never reaches
    # for a global and so tests can inject a fake
    model: str | None = None
