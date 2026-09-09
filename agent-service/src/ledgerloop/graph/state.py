"""InvoiceState and the schemas that bound it.

Three lifetimes, easy to collapse into one: state is durable per-thread
data, serialized into every checkpoint. Context is per-run, injected via
Runtime, and never checkpointed -- the only place non-serializable
dependencies (a DB connection, an HTTP client) may live. Config is
LangGraph's own plumbing, invisible to reducers, Store namespaces, and
evals. `tenant_id` lives in state, not just config, so it's visible to
all three.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel

from ledgerloop.graph.reducers import append_capped, dedupe_keep_severest, merge_by_index

Decision = Literal["auto_approve", "hold", "reject"]


class InvoiceFields(BaseModel):
    """Pydantic, not TypedDict: this is the extraction boundary, where a
    malformed value should fail loudly rather than silently become a
    policy decision. `bank_account`/`routing_number` must never leave the
    graph -- `DecisionResult` omits `fields` entirely."""

    vendor: str
    invoice_no: str
    po_number: str | None = None
    total: float = 0.0
    bank_account: str | None = None
    routing_number: str | None = None


class LineMatch(TypedDict):
    line_index: int
    po_quantity: float
    received_quantity: float
    invoice_quantity: float
    variance: float
    matched: bool


class ExceptionRecord(TypedDict):
    code: str
    severity: int
    message: str


class AuditEntry(TypedDict):
    node: str
    message: str


class InvoiceState(TypedDict, total=False):
    invoice_id: str
    tenant_id: str
    raw_text: str
    fields: InvoiceFields | None
    line_matches: Annotated[dict[int, LineMatch], merge_by_index]
    exceptions: Annotated[list[ExceptionRecord], dedupe_keep_severest]
    decision: Decision | None
    idempotency_key: str | None
    audit: Annotated[list[AuditEntry], append_capped(200)]
    messages: Annotated[list, add_messages]


@dataclass
class LedgerContext:
    """Per-run dependencies, injected via Runtime, never checkpointed.
    `tenant_id` is duplicated from state as a lookup key for resolving
    `erp_client`/`po_db`; state remains the source of truth."""

    tenant_id: str
    model: str = "balanced"
    erp_client: Any = None
    po_db: Any = None
    variance_tolerance: float = 0.02


class InvoiceRequest(TypedDict):
    invoice_id: str
    tenant_id: str
    raw_text: str


class DecisionResult(TypedDict):
    """No `raw_text`, no `fields` -- a caller gets the decision and audit
    trail, never the extracted document."""

    invoice_id: str
    tenant_id: str
    decision: Decision | None
    exceptions: list[ExceptionRecord]
    idempotency_key: str | None
    audit: list[AuditEntry]
