"""Per-run dependencies. Never serialized, never in state, re-supplied every run."""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from graph.erp import ErpClient, get_erp_client

from stubs.po_db import PurchaseOrderDB

class LedgerContext(BaseModel):
    tenant_id: str = "acme-corp"  # Default fallback or required string
    variance_tolerance: float = 0.05
    max_auto_approve: float = 50000.0
    investigator_tier: str = "strong"
    
    # Do not require non-serializable objects at instantiation
    # Provide defaults or instantiate them inside your node execution
   # Non-serializable runtime objects with default factories
    po_db: Any = Field(default_factory=PurchaseOrderDB)
    erp: Any = Field(default_factory=get_erp_client)
    
    class Config:
        arbitrary_types_allowed = True    


