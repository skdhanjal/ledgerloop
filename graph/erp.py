"""The ERP client, and its wiring into context.

The stub in stubs/erp.py is an HTTP service, but post_to_erp calls
erp.get_payment(key) as a plain method. Something has to sit between them -
this is it, and it is a DEPENDENCY, so it goes in context (Day 4), never state.

Why a Protocol rather than one concrete class: the tests inject a FakeERP with
no network, the money drill talks to the real stub, and production will
eventually talk to something with OAuth and a per-tenant base URL. All three
satisfy the same two methods.
"""
from functools import lru_cache
from typing import Protocol

import httpx


class ErpClient(Protocol):
    """Two methods. Read-before-write, then an idempotent write."""

    def get_payment(self, idempotency_key: str) -> dict | None: ...

    def post_payment(self, *, idempotency_key: str, tenant_id: str, vendor: str,
                     invoice_no: str, amount: float) -> dict: ...


class HttpErpClient:
    """Talks to stubs/erp.py - or to a real ERP with the same contract.

    Timeouts are explicit and short. This call sits inside a node with its own
    RetryPolicy (see fault_tolerance.py), so a hung request must fail fast
    enough for the retry to be worth anything rather than holding a worker.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._c = httpx.Client(base_url=base_url, timeout=timeout)

    def get_payment(self, idempotency_key: str) -> dict | None:
        r = self._c.get(f"/payments/{idempotency_key}")
        if r.status_code == 404:
            return None                 # nothing landed yet - the normal case
        r.raise_for_status()
        return r.json()

    def post_payment(self, *, idempotency_key: str, tenant_id: str, vendor: str,
                     invoice_no: str, amount: float) -> dict:
        r = self._c.post("/payments", json={
            "idempotency_key": idempotency_key, "tenant_id": tenant_id,
            "vendor": vendor, "invoice_no": invoice_no, "amount": amount,
        })
        # 4xx is a BUSINESS rejection (closed period, vendor on hold) and must
        # never be retried - retrying a rejected payment turns one failure into
        # three and an audit trail that reads like forcing it through.
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._c.close()

@lru_cache(maxsize=1)
def get_erp_client() -> ErpClient:
    """One place that knows where the ERP is."""
    import os
    return HttpErpClient(os.getenv("LEDGERLOOP_ERP_URL", "http://localhost:8000"))


# ------------------------------------------------------------------ context
# graph/context.py gains ONE field:
#
#     @dataclass
#     class LedgerContext:
#         tenant_id: str
#         po_db: "PurchaseOrderDB"
#         erp: ErpClient                  # <- new. A dependency, so: context.
#         variance_tolerance: float = 0.05
#         ...
#
# It is not Optional. A graph that can reach `post` without an ERP client is a
# graph that fails at the last node of a run someone waited two days for -
# fail at construction instead.
#
# graph/app.py - context_for() supplies it:
#
#     return LedgerContext(tenant_id=tenant_id,
#                          po_db=PurchaseOrderDB(),
#                          erp=get_erp_client(),        # <- new
#                          **cfg)
#
# Day 9's test_dependency_is_not_in_state still passes: an httpx.Client is not
# serializable, so if it ever drifts into state, that test fails loudly.
