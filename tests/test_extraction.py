"""Schema and failure-path tests. No API key - the model is a fake."""
import pytest
from pydantic import ValidationError

from graph.extraction import InvoiceFields, LineItem
from graph.extract_node import make_extract

GOOD = dict(vendor="Kestrel", invoice_no="INV-1", po_number="PO-4001",
            subtotal=2880.00, tax=518.40, total=3398.40,
            lines=[dict(sku="S1", quantity=12, unit_price=240.0, amount=2880.0)])


class FakeExtractor:
    """Stands in for model.with_structured_output(InvoiceFields)."""

    def __init__(self, payloads):
        self.payloads, self.calls = list(payloads), 0

    def invoke(self, messages):
        p = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return InvoiceFields(**p)          # raises ValidationError on bad data


class FakeModel:
    def __init__(self, extractor):
        self._e = extractor

    def with_structured_output(self, schema):
        return self._e


# ---- the schema itself -------------------------------------------------
def test_valid_invoice_parses():
    assert InvoiceFields(**GOOD).total == 3398.40


def test_lines_not_summing_to_subtotal_is_rejected():
    """A reading error - our fault, worth a retry."""
    bad = {**GOOD, "subtotal": 9999.0, "total": 10517.4, "tax": 518.4}
    with pytest.raises(ValidationError):
        InvoiceFields(**bad)


def test_tax_mismatch_is_reported_not_rejected():
    """A document defect - must survive extraction so the policy can catch it."""
    seeded = {**GOOD, "total": 3700.00}      # subtotal + tax != total
    fields = InvoiceFields(**seeded)         # does NOT raise
    assert fields.arithmetic_ok is False


def test_negative_total_is_rejected():
    with pytest.raises(ValidationError):
        InvoiceFields(**{**GOOD, "total": -1.0})


def test_unit_of_measure_is_optional_and_captured():
    line = LineItem(sku="S1", quantity=12, unit_price=150.0, amount=1800.0,
                    unit_of_measure="CASE")
    assert line.unit_of_measure == "CASE"


# ---- the failure path --------------------------------------------------
def test_first_attempt_success_does_not_retry():
    fake = FakeExtractor([GOOD])
    out = make_extract(FakeModel(fake))({"raw_text": "…"})
    assert out["extract_ok"] and fake.calls == 1


def test_extract_writes_subtotal_not_just_total():
    """CONTRACT. decide() compares the invoice NET against a tax-exclusive PO.
    If extraction stops writing `subtotal`, every clean invoice is held for a
    phantom price_variance equal to the tax rate - silently, with no error."""
    out = make_extract(FakeModel(FakeExtractor([GOOD])))({"raw_text": "…"})
    assert out["subtotal"] == GOOD["subtotal"]
    assert out["total"] == GOOD["total"]
    assert out["subtotal"] != out["total"], "subtotal must be net of tax"


def test_retry_recovers_after_a_validation_error():
    bad = {**GOOD, "subtotal": 1.0}
    fake = FakeExtractor([bad, GOOD])
    out = make_extract(FakeModel(fake))({"raw_text": "…"})
    assert out["extract_ok"] is True
    assert fake.calls == 2
    assert out["audit"][0]["retried"] is True


def test_two_failures_degrade_rather_than_raise():
    """The whole point of the day: no exception escapes the node."""
    bad = {**GOOD, "subtotal": 1.0}
    out = make_extract(FakeModel(FakeExtractor([bad, bad])))({"raw_text": "…"})
    assert out["extract_ok"] is False
    assert out["exceptions"][0]["code"] == "extraction_failed"


def test_retry_message_contains_the_specific_complaint():
    """A bare retry re-asks the same question. Feed back the actual error."""
    captured = []

    class Recorder(FakeExtractor):
        def invoke(self, messages):
            captured.append(messages[-1]["content"])
            return super().invoke(messages)

    bad = {**GOOD, "subtotal": 1.0}
    make_extract(FakeModel(Recorder([bad, GOOD])))({"raw_text": "…"})
    assert "subtotal" in captured[-1].lower()
