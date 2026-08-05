"""The pay/hold decision. A pure function - no state, no runtime, no model.

Everything here is arithmetic against thresholds, which is precisely why it is
Python and not a prompt. When a controller asks why invoice 4,471 was held, the
answer must be a rule you can point at, not a judgement you have to trust.
"""
from dataclasses import dataclass
from typing import Literal

Decision = Literal["auto_approve", "hold", "reject"]

@dataclass(frozen=True)
class PolicyInput:
    """Everything the decision depends on, gathered in one place."""
    total: float
    po_exists: bool
    price_variance: float          # fraction, e.g. 0.35 for 35% over PO
    qty_received_ratio: float      # 1.0 == everything invoiced was received
    is_duplicate: bool
    arithmetic_ok: bool


@dataclass(frozen=True)
class PolicyOutcome:
    decision: Decision
    reason: str
    exceptions: list[dict]


def _exc(code: str, severity: str, detail: str) -> dict:
    return {"code": code, "severity": severity, "detail": detail}


def evaluate(p: PolicyInput, tolerance: float,
             max_auto_approve: float) -> PolicyOutcome:
    """Order matters: the first matching rule wins, most severe first."""
    # 1. Never pay the same invoice twice. Not a hold - a reject.
    if p.is_duplicate:
        return PolicyOutcome("reject", "duplicate",
                             [_exc("duplicate", "high", "matches an earlier invoice")])

    # 2. No PO means nothing to match against. A human must look.
    if not p.po_exists:
        return PolicyOutcome("hold", "missing_po",
                             [_exc("missing_po", "high", "PO reference did not resolve")])

    exceptions: list[dict] = []

    # 3. Internal arithmetic must hold before comparing anything to a PO.
    if not p.arithmetic_ok:
        exceptions.append(_exc("tax_error", "medium", "subtotal + tax != total"))

    # 4. Price variance beyond tolerance.
    if p.price_variance > tolerance:
        exceptions.append(_exc("price_variance", "high",
                               f"{p.price_variance:.1%} over PO (tolerance {tolerance:.0%})"))

    # 5. Short shipment - we were billed for more than arrived.
    if p.qty_received_ratio < 1.0:
        exceptions.append(_exc("short_shipment", "high",
                               f"received {p.qty_received_ratio:.0%} of invoiced quantity"))

    if exceptions:
        return PolicyOutcome("hold", exceptions[0]["code"], exceptions)

    # 6. Clean, but above the auto-approve ceiling: policy, not a defect.
    if p.total > max_auto_approve:
        return PolicyOutcome("hold", "above_auto_approve_limit",
                             [_exc("above_auto_approve_limit", "low",
                                   f"total {p.total:,.2f} exceeds ceiling")])

    return PolicyOutcome("auto_approve", "clean", [])
