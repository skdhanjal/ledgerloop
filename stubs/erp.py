"""ERP stub with real idempotency semantics.

This stub is the most valuable piece of test infrastructure in the project:
it is what makes "we never double-pay" a testable claim rather than a hope.
A real ERP would do exactly this - reject a repeat key, replay the original.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="ERP stub")

_payments: dict[str, dict] = {}          # idempotency_key -> payment
_counter = 0


class PaymentRequest(BaseModel):
    idempotency_key: str
    tenant_id: str
    vendor: str
    invoice_no: str
    amount: float


@app.get("/payments/{idempotency_key}")
def get_payment(idempotency_key: str):
    """Read-before-write support. 404 means nothing landed yet."""
    payment = _payments.get(idempotency_key)
    if payment is None:
        raise HTTPException(404, "no payment for that key")
    return payment


@app.post("/payments")
def post_payment(req: PaymentRequest):
    """Idempotent create.

    A repeat of a known key is NOT an error - it returns the original payment
    with replayed=True. Returning 409 would be defensible too, but replay is
    kinder to a caller that crashed after writing and cannot tell which
    happened.
    """
    global _counter

    existing = _payments.get(req.idempotency_key)
    if existing:
        return {**existing, "replayed": True}

    _counter += 1
    payment = {"payment_id": f"PAY-{_counter:05d}", "amount": req.amount,
               "vendor": req.vendor, "invoice_no": req.invoice_no,
               "tenant_id": req.tenant_id, "replayed": False}
    _payments[req.idempotency_key] = payment
    return payment


@app.get("/_debug/payments")
def all_payments():
    """Used by the money test: assert exactly one payment exists."""
    return {"count": len(_payments), "payments": list(_payments.values())}
