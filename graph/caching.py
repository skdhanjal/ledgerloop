"""Cache keys: explicit, semantic, and scoped.

The DEFAULT key is a hash of the node's input state. That is unstable across
refactors (add an unrelated field, invalidate everything) and unscoped (two
tenants with identical input share a result). Write the key yourself.
"""
import hashlib

from langgraph.types import CachePolicy

from .tracing import PROMPT_VERSION


def _h(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


def extract_cache_key(state) -> str:
    """Extraction depends on: the document, the model, and the prompt.

    INCLUDED:
      raw_text        - the actual input
      prompt_version  - a prompt edit must invalidate every cached extraction,
                        or you spend an afternoon testing against stale results
                        and conclude your change did nothing
      model tier      - a retier changes the output

    EXCLUDED:
      tenant_id       - extraction is tenant-independent; the same PDF yields
                        the same fields for anyone. Including it would just
                        halve the hit rate.
    """
    return _h("extract", state.get("raw_text", ""), PROMPT_VERSION, "strong")


def po_lookup_cache_key(state) -> str:
    """Reference data. Short TTL because a PO can be amended upstream."""
    return _h("po", state.get("po_number", ""))


def investigate_cache_key(state) -> str:
    """Investigation IS tenant-scoped: the prompt carries tenant policy and
    the agent reads tenant vendor memory. A shared key would serve one
    tenant's reasoning to another."""
    return _h("investigate",
              state.get("invoice_id", ""),
              state.get("tenant_id", ""),
              str(sorted(e["code"] for e in state.get("exceptions", []))),
              PROMPT_VERSION)


CACHE_POLICIES = {
    # 1h: documents do not change, but do not hold results forever either
    "extract": CachePolicy(ttl=3600, key_func=extract_cache_key),
    # 5m: reference data can be amended upstream
    # "lookup_po": CachePolicy(ttl=300, key_func=po_lookup_cache_key),
    # dev only - see the note in wire_cache below
    "investigate": CachePolicy(ttl=1800, key_func=investigate_cache_key),
}

NEVER_CACHE = {"post_to_erp", "approval_gate", "intake"}


def wire_cache(builder, *, dev: bool):
    """Caching is a DEVELOPMENT accelerator here, not a production feature.

    In production the investigator's output is what a human reads to decide a
    payment - serving a 30-minute-old cached verdict for a re-submitted invoice
    is defensible only if you are certain nothing upstream changed. We are not.

    Extraction caching is safe in production; investigation caching is not.
    """
    policies = CACHE_POLICIES if dev else {
        k: v for k, v in CACHE_POLICIES.items() if k != "investigate"}

    for node, policy in policies.items():
        builder.nodes[node].cache_policy = policy
    return builder
