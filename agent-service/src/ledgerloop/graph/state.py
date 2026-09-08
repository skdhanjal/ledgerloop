"""InvoiceState: the durable, per-thread pipeline state, plus the
input/output/context schemas that bound what a caller sends in, what they
get back, and what non-serializable dependencies a node can reach.

Three different lifetimes, easy to collapse into one if you're not
careful (Day 3's concept note):

- STATE   (`InvoiceState`)    durable, per-thread, serialized into every
                                checkpoint from Day 9 onward.
- CONTEXT (`LedgerContext`)   per-run dependencies, injected via
                                `Runtime[LedgerContext]`, never checkpointed --
                                the only place a DB connection or an HTTP
                                client is allowed to live.
- CONFIG  (`RunnableConfig`)  LangGraph plumbing (`thread_id`, recursion
                                limit). Never put anything here that a
                                reducer, a Store namespace, or an eval needs
                                to see -- `tenant_id` lives in STATE for
                                exactly that reason (see docs/DECISIONS.md,
                                Day 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel

from ledgerloop.graph.reducers import append_capped, dedupe_keep_severest, merge_by_index

Decision = Literal["auto_approve", "hold", "reject"]


class InvoiceFields(BaseModel):
    """Extracted invoice fields. Day 8's real extractor fills this in;
    Day 2/3 use a hardcoded stand-in. Pydantic, not TypedDict, because
    this crosses the extraction boundary and we want validation on the
    way in -- a malformed `total` should fail loudly, not silently
    become a policy decision.

    `bank_account` / `routing_number` are payment-routing fields some
    invoices carry for wire transfer. They must never leave the graph
    through `invoke()` -- `DecisionResult` (the output schema below)
    omits `fields` entirely on purpose, and Day 3's test proves it.
    """

    vendor: str
    invoice_no: str
    po_number: str | None = None
    total: float = 0.0
    bank_account: str | None = None
    routing_number: str | None = None


class LineMatch(TypedDict):
    """One line item's three-way-match result. Day 14 fans out one matcher
    branch per line, keyed by `line_index`, writing into `line_matches`
    below -- this is the payload each branch produces."""

    line_index: int
    po_quantity: float
    received_quantity: float
    invoice_quantity: float
    variance: float
    matched: bool


class ExceptionRecord(TypedDict):
    """One policy exception. `code` matches Day 5's rule-cascade vocabulary
    (see `ledgerloop.data.models.EXCEPTION_TYPES`); `severity` is what
    `dedupe_keep_severest` compares when the same code is raised twice."""

    code: str
    severity: int
    message: str


class AuditEntry(TypedDict):
    """One audit-trail entry. Structured, not a bare string, so Day 26's
    audit log can filter or sort by node without parsing free text."""

    node: str
    message: str


class InvoiceState(TypedDict, total=False):
    """The full pipeline state, durable across every checkpoint. Every
    field here is serialized on every superstep -- see the module
    docstring for what does *not* belong here."""

    invoice_id: str
    tenant_id: str  # first-class in state, not just config -- see module docstring
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
    """Per-run dependencies, injected via `Runtime[LedgerContext]` and
    never checkpointed. `tenant_id` is duplicated here even though it also
    lives in state: a node resolving `erp_client` / `po_db` from a
    connection pool needs it as a lookup key at call time, but state --
    not context -- is the source of truth a reducer, a Store namespace,
    or an eval can see."""

    tenant_id: str
    model: str = "balanced"
    erp_client: Any = None
    po_db: Any = None
    variance_tolerance: float = 0.02


class InvoiceRequest(TypedDict):
    """What a caller sends in to `invoke()`. Deliberately narrow --
    everything else in `InvoiceState` starts empty and is built up by
    the graph as it runs."""

    invoice_id: str
    tenant_id: str
    raw_text: str


class DecisionResult(TypedDict):
    """What `invoke()` returns. No `raw_text`, no `fields` (and therefore
    no bank details), no `messages` -- a caller gets the decision and the
    audit trail, never the extracted document or the conversation that
    produced it."""

    invoice_id: str
    tenant_id: str
    decision: Decision | None
    exceptions: list[ExceptionRecord]
    idempotency_key: str | None
    audit: list[AuditEntry]
