"""Fan-out tests. Pure functions and a fake PO db - no model, milliseconds."""
import pytest

from graph.fanout import fan_out_lines, reconcile
from graph.matching import match_line

PO_LINE = {"sku": "S1", "quantity": 30, "unit_price": 85.0}


def inv_line(qty=30, price=85.0, sku="S1", uom=None):
    return {"sku": sku, "quantity": qty, "unit_price": price,
            "amount": qty * price, "unit_of_measure": uom}


def payload(**over):
    return {"line_index": 0, "line": inv_line(), "po_line": PO_LINE,
            "receipt_qty": 30, "tolerance": 0.05, **over}


# ---- one worker, in isolation -----------------------------------------
def test_matching_line_is_ok():
    out = match_line(payload())["line_matches"][0]
    assert out["status"] == "ok"


def test_price_variance_detected():
    out = match_line(payload(line=inv_line(price=114.75)))["line_matches"][0]
    assert out["status"] == "price_variance"
    assert out["price_variance"] > 0.3


def test_short_shipment_detected():
    out = match_line(payload(receipt_qty=25))["line_matches"][0]
    assert out["status"] == "short_shipment"
    assert out["qty_ratio"] < 1.0


def test_sku_not_on_po():
    out = match_line(payload(po_line=None))["line_matches"][0]
    assert out["status"] == "no_po_line"


def test_unit_of_measure_is_normalised_not_flagged():
    """The Exercise 1.2 case: 12 CASES @ 1020.00 == 144 units @ 85.00.

    A naive matcher sees a 92% quantity shortfall AND a 1100% price variance.
    Both are wrong; the money is exactly right.
    """
    po = {"sku": "S1", "quantity": 144, "unit_price": 85.0}
    out = match_line(payload(line=inv_line(qty=12, price=1020.0, uom="CASE"),
                             po_line=po, receipt_qty=144))["line_matches"][0]
    assert out["status"] == "ok"
    assert out["uom_normalised"] is True


# ---- fan-out width ----------------------------------------------------
class FakeDB:
    def get_po(self, n):
        return {"lines": [PO_LINE]}

    def get_receipt(self, n):
        return {"lines": [{"sku": "S1", "quantity_received": 30}]}


def state_with(n_lines):
    return {"po_number": "PO-1",
            "fields": {"lines": [inv_line() for _ in range(n_lines)]}}


def test_one_send_per_line():
    sends = fan_out_lines(state_with(7), FakeDB(), 0.05)
    assert len(sends) == 7
    assert [s.arg["line_index"] for s in sends] == list(range(7))


def test_width_is_capped():
    from graph.matching import MAX_PARALLEL_LINES
    sends = fan_out_lines(state_with(200), FakeDB(), 0.05)
    assert len(sends) == MAX_PARALLEL_LINES


def test_worker_payload_excludes_the_invoice():
    """Thirty workers each carrying raw_text would be pure waste."""
    send = fan_out_lines(state_with(1), FakeDB(), 0.05)[0]
    assert "raw_text" not in send.arg
    assert "messages" not in send.arg


# ---- the join ---------------------------------------------------------
def m(idx, status="ok", var=0.0, ratio=1.0):
    return {"line_index": idx, "sku": f"S{idx}", "status": status,
            "price_variance": var, "qty_ratio": ratio}


def test_reconcile_takes_the_worst_across_lines():
    out = reconcile({"line_matches": [m(0), m(1, "price_variance", var=0.35),
                                      m(2, "short_shipment", ratio=0.8)]})
    assert out["worst_price_variance"] == 0.35
    assert out["worst_qty_ratio"] == 0.8
    assert out["failing_lines"] == [1, 2]


def test_reconcile_is_order_independent():
    """Branches land in whatever order they finish - defer does not sort them."""
    a = reconcile({"line_matches": [m(0), m(1, "price_variance", var=0.2)]})
    b = reconcile({"line_matches": [m(1, "price_variance", var=0.2), m(0)]})
    assert a["worst_price_variance"] == b["worst_price_variance"]


def test_reconcile_handles_zero_lines():
    assert reconcile({"line_matches": []})["reconciled"] is False
