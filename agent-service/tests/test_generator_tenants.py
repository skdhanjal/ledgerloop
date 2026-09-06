import json

import pytest

from ledgerloop.data.generate import generate


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("dataset")
    generate(n_tenants=3, n_invoices=60, seed=42, out_dir=out)
    return out


def load(path):
    return json.loads(path.read_text())


def test_three_tenants_with_distinct_rosters_and_tolerances(dataset):
    tenants = [load(p) for p in sorted(dataset.glob("*/tenant.json"))]
    assert len(tenants) == 3

    tolerances = {t["variance_tolerance"] for t in tenants}
    ceilings = {t["auto_approve_ceiling"] for t in tenants}
    assert len(tolerances) == 3, "tenants must have genuinely different variance tolerances"
    assert len(ceilings) == 3, "tenants must have genuinely different auto-approve ceilings"

    vendor_name_sets = [{v["name"] for v in t["vendors"]} for t in tenants]
    for i in range(len(vendor_name_sets)):
        for j in range(i + 1, len(vendor_name_sets)):
            assert vendor_name_sets[i] != vendor_name_sets[j], "vendor rosters must differ"


def _find_gr_for_po(tenant_dir, po_number):
    for path in (tenant_dir / "goods_receipts").glob("*.json"):
        gr = load(path)
        if gr["po_number"] == po_number:
            return gr
    raise AssertionError(f"no goods receipt found for {po_number}")


def _assert_defect_present(tenant_dir, invoice, exc_type, ceiling, tolerance, all_invoice_nos):
    """The self-consistency check: the *actual* defect this exception_type
    promises must really be present in the constructed documents."""
    if exc_type == "duplicate":
        key = (invoice["vendor"], invoice["invoice_no"])
        assert all_invoice_nos.count(key) >= 2

    elif exc_type == "missing_po":
        po_path = tenant_dir / "purchase_orders" / f"{invoice['po_number']}.json"
        assert not po_path.exists()

    elif exc_type == "arithmetic_error":
        line_sum = round(sum(line["line_total"] for line in invoice["lines"]), 2)
        assert abs(line_sum - invoice["subtotal"]) > 0.01

    elif exc_type == "price_variance":
        po = load(tenant_dir / "purchase_orders" / f"{invoice['po_number']}.json")
        po_prices = {line["description"]: line["unit_price"] for line in po["lines"]}
        deviations = []
        for line in invoice["lines"]:
            po_price = po_prices[line["description"]]
            deviations.append(abs(line["unit_price"] - po_price) / po_price)
        assert max(deviations) > tolerance

    elif exc_type == "short_shipment":
        gr = _find_gr_for_po(tenant_dir, invoice["po_number"])
        pairs = zip(gr["lines"], invoice["lines"], strict=True)
        shorted = any(gl["quantity_received"] < il["quantity"] for gl, il in pairs)
        assert shorted

    elif exc_type == "over_ceiling":
        assert invoice["total"] > ceiling

    else:
        raise AssertionError(f"unknown exception_type: {exc_type}")


def _assert_clean_matches_exactly(tenant_dir, invoice, ceiling):
    assert invoice["total"] <= ceiling
    po = load(tenant_dir / "purchase_orders" / f"{invoice['po_number']}.json")
    gr = _find_gr_for_po(tenant_dir, invoice["po_number"])
    invoice_totals = [line["line_total"] for line in invoice["lines"]]
    po_totals = [line["line_total"] for line in po["lines"]]
    assert invoice_totals == po_totals
    for gr_line, inv_line in zip(gr["lines"], invoice["lines"], strict=True):
        assert gr_line["quantity_received"] == inv_line["quantity"]


def test_ground_truth_matches_the_actual_constructed_documents(dataset):
    checked_types = set()

    for tenant_dir in sorted(p for p in dataset.iterdir() if p.is_dir()):
        tenant = load(tenant_dir / "tenant.json")
        ceiling = tenant["auto_approve_ceiling"]
        tolerance = tenant["variance_tolerance"]

        gt_files = sorted((tenant_dir / "ground_truth").glob("*.json"))
        all_invoice_nos = [
            (inv["vendor"], inv["invoice_no"])
            for inv in (load(p) for p in sorted((tenant_dir / "invoices").glob("*.json")))
        ]

        for gt_path in gt_files:
            gt = load(gt_path)
            invoice = load(tenant_dir / "invoices" / f"{gt['invoice_id']}.json")
            exc_type = gt["exception_type"]
            checked_types.add(exc_type)

            if exc_type == "clean":
                assert gt["expected_decision"] == "auto_approve"
                assert gt["expected_exceptions"] == []
                _assert_clean_matches_exactly(tenant_dir, invoice, ceiling)
            else:
                assert gt["expected_decision"] == ("reject" if exc_type == "duplicate" else "hold")
                assert gt["expected_exceptions"] == [exc_type]
                _assert_defect_present(
                    tenant_dir, invoice, exc_type, ceiling, tolerance, all_invoice_nos
                )

    # Every exception type from the vocabulary actually got exercised somewhere.
    assert checked_types == {
        "clean",
        "duplicate",
        "missing_po",
        "arithmetic_error",
        "price_variance",
        "short_shipment",
        "over_ceiling",
    }
