"""Extraction schema and the model call that fills it.

Boundary rule from Day 4: Pydantic here because model output is untrusted input
arriving from outside. TypedDict stays for the graph's internal state.
"""
from pydantic import BaseModel, Field, model_validator

TOLERANCE = 0.01          # one paisa

class LineItem(BaseModel):
    sku: str
    description: str = ""
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    amount: float = Field(ge=0)
    unit_of_measure: str | None = Field(
        default=None,
        description="If the line bills in cases/boxes rather than individual "
                    "units, state it here (e.g. 'CASE'). Null if plain units.")


class InvoiceFields(BaseModel):
    """What we need off the document. Descriptions are prompt engineering -
    the model sees every one of them."""

    vendor: str = Field(description="Vendor company name exactly as printed")
    invoice_no: str = Field(description="The vendor's invoice number")
    po_number: str | None = Field(
        default=None, description="PO reference if present, else null")
    currency: str = Field(default="INR")
    subtotal: float = Field(gt=0, description="Sum before tax, as printed")
    tax: float = Field(ge=0)
    total: float = Field(gt=0, description="Total due as printed on the invoice")
    lines: list[LineItem] = Field(min_length=1)

    @model_validator(mode="after")
    def lines_must_sum_to_subtotal(self) -> "InvoiceFields":
        """A READING check, not a document check.

        If the extracted line amounts do not add up to the extracted subtotal,
        the model misread something - a dropped line, a transposed digit. This
        is our fault and worth a retry.

        Deliberately NOT checked here: subtotal + tax == total. That mismatch is
        a real defect on real invoices (our generator seeds it as tax_error), so
        raising would make extraction fail on precisely the invoices whose defect
        we most want to detect. It is recorded as a finding instead - see
        arithmetic_ok below.
        """
        line_sum = sum(l.amount for l in self.lines)
        if abs(line_sum - self.subtotal) > TOLERANCE:
            raise ValueError(
                f"line amounts sum to {line_sum:.2f} but subtotal is "
                f"{self.subtotal:.2f} - re-read the line items")
        return self

    @property
    def arithmetic_ok(self) -> bool:
        """Document-level check, reported rather than enforced."""
        return abs((self.subtotal + self.tax) - self.total) <= TOLERANCE


class ExceptionVerdict(BaseModel):
    """The investigator's output. Replaces Day 6's free-text block.

    A router can branch on this and a Day 22 judge can grade it field by field,
    neither of which is true of prose.
    """
    root_cause: str = Field(description="One sentence. What actually happened.")
    evidence: list[str] = Field(
        description="Tool findings relied on, one per item. Do not include "
                    "anything you did not verify with a tool.")
    recommendation: str = Field(description="One of: hold, reject, approve")
    confidence: float = Field(ge=0, le=1)
