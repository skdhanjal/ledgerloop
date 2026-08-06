"""Memory and trimming tests. No API key - fake store, fake embeddings."""
import pytest
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.store.memory import InMemoryStore

from graph.memory import (format_for_prompt, recall_vendor,
                          remember_resolution, vendor_ns)


@pytest.fixture
def store():
    return InMemoryStore()          # no index -> exact-key lookups, no embeddings


def seed(store, tenant, vendor, code="short_shipment"):
    remember_resolution(store, tenant, vendor, exception_code=code,
                        root_cause="vendor ships partial by agreement",
                        resolution="hold", invoice_id="INV-1")


# ---- isolation: the property everything on Day 26 depends on ----------
def test_namespace_puts_tenant_first():
    assert vendor_ns("acme-corp", "Kestrel")[0] == "acme-corp"


def test_one_tenant_cannot_read_another(store):
    seed(store, "acme-corp", "Kestrel")
    assert store.get(vendor_ns("acme-corp", "Kestrel"), "resolution:short_shipment")
    assert store.get(vendor_ns("globex-ltd", "Kestrel"), "resolution:short_shipment") is None


def test_same_vendor_name_different_tenants_stay_separate(store):
    """Two clients can both buy from Kestrel. Their histories must not merge."""
    seed(store, "acme-corp", "Kestrel", code="price_variance")
    seed(store, "globex-ltd", "Kestrel", code="missing_po")
    acme = store.get(vendor_ns("acme-corp", "Kestrel"), "resolution:missing_po")
    assert acme is None


# ---- write discipline -------------------------------------------------
def test_repeat_exception_updates_rather_than_accumulates(store):
    for i in range(5):
        remember_resolution(store, "t", "V", exception_code="short_shipment",
                            root_cause=f"cause {i}", resolution="hold",
                            invoice_id=f"INV-{i}")
    items = store.search(vendor_ns("t", "V"))
    assert len(items) == 1
    assert items[0].value["last_seen_invoice"] == "INV-4"


def test_unknown_vendor_returns_empty_not_error(store):
    assert recall_vendor(store, "t", "Nobody Ltd", query="anything") == []


def test_missing_vendor_name_is_handled(store):
    assert recall_vendor(store, "t", "", query="anything") == []


def test_prompt_format_is_explicit_about_having_no_history():
    assert "No prior history" in format_for_prompt([])


# ---- the pairing rule -------------------------------------------------
def naive_tail(messages, n):
    """The tempting one-liner from the predict prompt."""
    return [messages[0]] + messages[-n:]


def has_orphaned_tool_message(messages) -> bool:
    ids = {tc["id"] for m in messages
           for tc in (getattr(m, "tool_calls", None) or [])}
    return any(m.type == "tool" and m.tool_call_id not in ids for m in messages)


HISTORY = [
    SystemMessage("system"),
    HumanMessage("investigate INV-1"),
    AIMessage("", tool_calls=[{"name": "lookup_po", "args": {}, "id": "a"}]),
    ToolMessage("PO found", tool_call_id="a"),
    AIMessage("", tool_calls=[{"name": "lookup_receipt", "args": {}, "id": "b"}]),
    ToolMessage("receipt found", tool_call_id="b"),
    AIMessage("ROOT CAUSE: ..."),
]


def test_naive_slicing_can_orphan_a_tool_message():
    """Slicing at n=4 lands between an AIMessage and its ToolMessage."""
    assert has_orphaned_tool_message(naive_tail(HISTORY, 4))


def test_slicing_on_a_pair_boundary_is_safe():
    assert not has_orphaned_tool_message(naive_tail(HISTORY, 5))
