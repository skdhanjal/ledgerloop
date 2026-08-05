"""The extract node: model call, validation, one retry, then degrade."""
from pydantic import ValidationError

from .extraction import InvoiceFields

PROMPT = """Extract the fields from this invoice exactly as printed.

Do not calculate values that are not on the document - if the printed total
does not match subtotal plus tax, report BOTH as printed. Reporting the
document faithfully matters more than making it consistent.

If a line bills in cases or boxes rather than individual units, set
unit_of_measure for that line.

INVOICE:
{raw_text}"""


def make_extract(model):
    """Injected model, so tests pass a fake (Day 4's boundary, again)."""
    extractor = model.with_structured_output(InvoiceFields)

    def extract(state) -> dict:
        attempt = state.get("extract_attempts", 0) + 1
        messages = [{"role": "user", "content": PROMPT.format(raw_text=state["raw_text"])}]

        for tries in range(2):                 # original + one informed retry
            try:
                fields: InvoiceFields = extractor.invoke(messages)
            except ValidationError as e:
                if tries == 1:
                    break                      # fall through to degrade
                # Feed back the SPECIFIC complaint. A bare retry re-asks the
                # same question and usually gets the same answer.
                messages.append({
                    "role": "user",
                    "content": (f"That failed validation: {e.errors()[0]['msg']}\n"
                                f"Re-read the invoice and correct it.")})
                continue

            return {
                "extract_attempts": attempt,
                "extract_ok": True,
                "vendor": fields.vendor,
                "invoice_no": fields.invoice_no,
                "po_number": fields.po_number,
                "subtotal": fields.subtotal,   # NET - decide() compares this
                "tax": fields.tax,             # to the (tax-exclusive) PO
                "total": fields.total,         # GROSS - never vs a PO
                "arithmetic_ok": fields.arithmetic_ok,
                "fields": fields.model_dump(),
                "audit": [{"node": "extract", "event": "extracted",
                           "attempt": attempt, "retried": tries > 0}],
            }

        # Degraded path: a real result a human can act on, NOT an exception.
        return {
            "extract_attempts": attempt,
            "extract_ok": False,
            "exceptions": [{"code": "extraction_failed", "severity": "high",
                            "detail": "schema validation failed twice"}],
            "audit": [{"node": "extract", "event": "extraction_degraded",
                       "attempt": attempt}],
        }

    return extract
