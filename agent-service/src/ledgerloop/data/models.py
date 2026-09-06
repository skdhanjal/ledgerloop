from pydantic import BaseModel


class LineItem(BaseModel):
    description: str
    quantity: int
    uom: str
    unit_price: float
    line_total: float


class CatalogItem(BaseModel):
    description: str
    uom: str
    unit_price: float


class Vendor(BaseModel):
    vendor_id: str
    name: str
    catalog: list[CatalogItem]


class Tenant(BaseModel):
    tenant_id: str
    name: str
    variance_tolerance: float
    auto_approve_ceiling: float
    vendors: list[Vendor]


class Invoice(BaseModel):
    invoice_id: str
    tenant_id: str
    vendor: str
    invoice_no: str
    po_number: str | None
    date: str
    currency: str = "USD"
    lines: list[LineItem]
    subtotal: float
    tax: float
    total: float
    content_hash: str = ""


class PurchaseOrder(BaseModel):
    po_number: str
    tenant_id: str
    vendor: str
    lines: list[LineItem]
    content_hash: str = ""


class GoodsReceiptLine(BaseModel):
    description: str
    quantity_received: int


class GoodsReceipt(BaseModel):
    gr_number: str
    tenant_id: str
    po_number: str
    lines: list[GoodsReceiptLine]
    content_hash: str = ""


class GroundTruth(BaseModel):
    invoice_id: str
    tenant_id: str
    exception_type: str
    expected_decision: str
    expected_exceptions: list[str]
    content_hash: str = ""


# The exception vocabulary matches Day 5's policy cascade exactly
# (docs/LedgerLoop_Master_Build_Document.md, "Day 5 - ... Deterministic Policy Gate"),
# so labeled cases exist for the policy engine and evals from day one.
EXCEPTION_TYPES = [
    "duplicate",
    "missing_po",
    "arithmetic_error",
    "price_variance",
    "short_shipment",
    "over_ceiling",
]

# Fixed type -> decision mapping, matching Day 5's rule cascade.
DECISION_FOR_TYPE = {
    "clean": "auto_approve",
    "duplicate": "reject",
    "missing_po": "hold",
    "arithmetic_error": "hold",
    "price_variance": "hold",
    "short_shipment": "hold",
    "over_ceiling": "hold",
}
