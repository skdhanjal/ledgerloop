"""The public contract. Pydantic here because this IS a boundary."""
from typing import Literal

from pydantic import BaseModel, Field

class InvoiceRequest(BaseModel):
    """What a caller may send. Anything else is rejected."""
    invoice_path: str = Field(description="Path to the invoice text file")


class DecisionResult(BaseModel):
    """What a caller gets back. Deliberately small.

    Note what is NOT here: raw_text (vendor bank details), internal notes,
    placeholder fields. Adding a key here is an API change; adding one to
    InvoiceState is not. That asymmetry is the entire point.
    """
    invoice_id: str
    tenant_id: str
    decision: Literal["auto_approve", "hold", "reject"]
    reason: str
    total: float
    exceptions: list[dict] = [],
    investigation: str
