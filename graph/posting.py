"""The one node that moves money. Nothing else lives here.

Every line in this function re-executes on retry, resume, or a time-travel
fork. Keeping it minimal is the first line of defence; the key is the second.
"""
import hashlib

from langgraph.runtime import Runtime

from graph.events import ProgressEvent

from .context import LedgerContext
from .state import InvoiceState

def idempotency_key(state: InvoiceState, tenant_id: str) -> str:
    """Narrow enough to distinguish different payments, broad enough to
    recognise a retry of the same one.

    INCLUDED, and why:
      tenant_id   - two tenants can both receive invoice INV-1001
      vendor      - two vendors can both use invoice number 42
      invoice_no  - the vendor's identifier for this bill
      amount      - a CORRECTED amount is a different payment, not a retry.
                    Without it, a controller fixing 3,398 -> 33,980 would
                    replay the original posting and the system would believe
                    the invoice was settled.

    DELIBERATELY EXCLUDED:
      checkpoint_id, timestamps, uuid4 - anything that changes between
      retries of the same payment defeats the entire mechanism.
    """
    amount_cents = int(round(state.get("total", 0.0) * 100))
    raw = "|".join([
        tenant_id,
        state.get("vendor", ""),
        state.get("invoice_no", ""),
        str(amount_cents),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def post_to_erp(state: InvoiceState, runtime: Runtime[LedgerContext]) -> dict:
    key = idempotency_key(state, runtime.context.tenant_id)
    erp = runtime.context.erp
    print(f"Creating payment for key {key}")

    # 1. CHECK REALITY. A previous attempt may have landed before we died.
    #    Cheap, and it returns the original payment_id rather than an error.
    existing = erp.get_payment(key)
    if existing:
        return {
            "posted": True,
            "payment_id": existing["payment_id"],
            "audit": [{"node": "post_to_erp", "event": "already_posted",
                       "payment_id": existing["payment_id"],
                       "idempotency_key": key}],
        }

    # 2. WRITE. The key makes this safe even if two workers raced past step 1.
    result = erp.post_payment(
        idempotency_key=key,
        tenant_id=runtime.context.tenant_id,
        vendor=state.get("vendor", ""),
        invoice_no=state.get("invoice_no", ""),
        amount=state.get("total", 0.0),
    )

    runtime.stream_writer(ProgressEvent(stage="post", 
        label=f"Posting payment for {state.get("invoice_no", "")} with payment id {result["payment_id"]}").model_dump())

    # 3. RECORD before returning, so the audit trail survives a crash here.
    return {
        "posted": True,
        "payment_id": result["payment_id"],
        "audit": [{"node": "post_to_erp",
                   "event": "replayed" if result.get("replayed") else "posted",
                   "payment_id": result["payment_id"],
                   "idempotency_key": key,
                   "amount": state.get("total")}],
    }


def posting_failed(state: InvoiceState, error) -> dict:
    """error_handler: runs only after every retry is exhausted.

    Degrades to a held invoice with an actionable reason. Never re-raises -
    a dead thread helps nobody, and this invoice needs a human either way.
    """
    return {
        "posted": False,
        "decision": "hold",
        "reason": "posting_failed",
        "exceptions": [{"code": "posting_failed", "severity": "high",
                        "detail": f"{type(error).__name__}: {error}"}],
        "audit": [{"node": "post_to_erp", "event": "failed_after_retries",
                   "error": type(error).__name__}],
    }
