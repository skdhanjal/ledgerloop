"""Router and policy tests. Eight handcrafted cases, zero LLM calls, milliseconds."""
import pytest

from graph.policy import PolicyInput, evaluate
from graph.routers import (MAX_EXTRACT_ATTEMPTS, route_after_decide,
                           route_after_extract)

CLEAN = dict(total=3400.0, po_exists=True, price_variance=0.0,
             qty_received_ratio=1.0, is_duplicate=False, arithmetic_ok=True)


def ev(**over):
    return evaluate(PolicyInput(**{**CLEAN, **over}),
                    tolerance=0.05, max_auto_approve=50_000)


# ---- policy: one test per rule, in precedence order --------------------
def test_clean_invoice_auto_approves():
    assert ev().decision == "auto_approve"


def test_duplicate_rejects_not_holds():
    assert ev(is_duplicate=True).decision == "reject"


def test_duplicate_outranks_everything_else():
    """Precedence matters: a duplicate with a variance is still a reject."""
    assert ev(is_duplicate=True, price_variance=0.9, po_exists=False).decision == "reject"


def test_missing_po_holds():
    out = ev(po_exists=False)
    assert (out.decision, out.reason) == ("hold", "missing_po")


def test_variance_inside_tolerance_still_approves():
    assert ev(price_variance=0.04).decision == "auto_approve"


def test_variance_outside_tolerance_holds():
    assert ev(price_variance=0.06).reason == "price_variance"


def test_short_shipment_holds():
    assert ev(qty_received_ratio=0.83).reason == "short_shipment"


def test_clean_but_over_ceiling_holds():
    out = ev(total=60_000.0)
    assert (out.decision, out.reason) == ("hold", "above_auto_approve_limit")


def test_tolerance_is_injectable_not_hardcoded():
    """Same invoice, stricter tenant policy, different answer."""
    p = PolicyInput(**{**CLEAN, "price_variance": 0.03})
    assert evaluate(p, tolerance=0.05, max_auto_approve=50_000).decision == "auto_approve"
    assert evaluate(p, tolerance=0.00, max_auto_approve=50_000).decision == "hold"


# ---- routers -----------------------------------------------------------
def test_router_sends_success_forward():
    assert route_after_extract({"extract_ok": True}) == "decide"


def test_router_retries_while_budget_remains():
    assert route_after_extract({"extract_ok": False, "extract_attempts": 1}) == "extract"


def test_router_escalates_when_budget_spent():
    assert route_after_extract(
        {"extract_ok": False, "extract_attempts": MAX_EXTRACT_ATTEMPTS}) == "escalate"


@pytest.mark.parametrize("decision,expected", [
    ("auto_approve", "post"), ("hold", "investigate"), ("reject", "investigate")])
def test_decide_router(decision, expected):
    assert route_after_decide({"decision": decision}) == expected


def test_routers_do_not_mutate_state():
    """They may be re-executed, so they must be pure."""
    s = {"extract_ok": False, "extract_attempts": 1}
    snapshot = dict(s)
    route_after_extract(s)
    assert s == snapshot
