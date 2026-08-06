"""Long-term memory: what LedgerLoop remembers about vendors, across invoices.

Namespaces are ALWAYS (tenant_id, ...). That tuple is the isolation boundary -
a query cannot accidentally omit it the way a WHERE clause can.
"""
from typing import Any

MAX_MEMORIES_PER_VENDOR = 20

def vendor_ns(tenant_id: str, vendor: str) -> tuple[str, ...]:
    return (tenant_id, "vendors", vendor)


def policy_ns(tenant_id: str) -> tuple[str, ...]:
    return (tenant_id, "house_rules")


def recall_vendor(store, tenant_id: str, vendor: str, query: str,
                  limit: int = 3) -> list[dict[str, Any]]:
    """Semantic search over what we know about this vendor.

    Returns [] rather than raising when nothing is known - a first-time vendor
    is a normal case, not an error, and the investigator handles an empty list
    fine. (Day 6's raise-vs-return reasoning, applied to memory.)
    """
    if not vendor:
        return []
    hits = store.search(vendor_ns(tenant_id, vendor), query=query, limit=limit)
    return [h.value for h in hits]


def remember_resolution(store, tenant_id: str, vendor: str, *,
                        exception_code: str, root_cause: str,
                        resolution: str, invoice_id: str) -> None:
    """Write one memory, keyed so a repeat of the same exception UPDATES rather
    than accumulates. Otherwise thirty short shipments become thirty near
    identical memories and semantic search returns the same thing three times.
    """
    store.put(
        vendor_ns(tenant_id, vendor),
        key=f"resolution:{exception_code}",
        value={
            "text": f"{exception_code}: {root_cause} -> {resolution}",
            "exception_code": exception_code,
            "root_cause": root_cause,
            "resolution": resolution,
            "last_seen_invoice": invoice_id,
        },
    )


def format_for_prompt(memories: list[dict]) -> str:
    if not memories:
        return "No prior history with this vendor."
    lines = "\n".join(f"- {m['text']}" for m in memories)
    return f"What we know about this vendor:\n{lines}"
