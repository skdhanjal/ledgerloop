"""The human approval gate.

CRITICAL: interrupt() is the FIRST statement. On resume the node re-executes
from the top (Day 9 replay semantics), so anything above the interrupt runs
twice - two audit rows, two emails, two of whatever you did. If work must
happen before the pause, put it in a separate node so it commits its own
super-step.
"""
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from graph.context import LedgerContext
from graph.memory import remember_resolution

from .state import InvoiceState

EDITABLE = ["total", "po_number", "vendor"]


def needs_human(state: InvoiceState, max_auto_approve: float) -> bool:
    return (state.get("decision") != "auto_approve"
            or state.get("total", 0) > max_auto_approve)


def approval_gate(state: InvoiceState, runtime: Runtime[LedgerContext]) -> dict:
    """Pause for a controller. Everything below runs only after resume."""
    verdict = state.get("verdict") or {}
    ctx = runtime.context
    tenant = ctx.tenant_id
    vendor = state.get("vendor")

    decision = interrupt({
        # identity - so the controller can find this in the ERP
        "invoice_id": state.get("invoice_id"),
        "vendor": vendor,
        "invoice_no": state.get("invoice_no"),
        "total": state.get("total"),
        "currency": "INR",

        # the machine's decision and why
        "decision": state.get("decision"),
        "reason": state.get("reason"),
        "exceptions": state.get("exceptions", []),

        # the investigator's case
        "root_cause": verdict.get("root_cause"),
        "evidence": verdict.get("evidence", []),
        "confidence": verdict.get("confidence"),

        # the UI contract: what is legal here, so the frontend need not guess
        "allowed_actions": ["approve", "edit", "reject"],
        "editable_fields": EDITABLE,

        # deliberately absent: raw_text. Bank details, large, and streamed
        # to a browser from Day 20.
    })

    action = decision.get("action")
    note = decision.get("note", "")

    if action == "approve":
        if runtime.store and verdict.confidence >= 0.7 and state.get("exceptions"):
            remember_resolution(
                runtime.store, tenant, vendor,
                exception_code=state["exceptions"][0]["code"],
                root_cause=verdict.root_cause,
                resolution=verdict.recommendation,
                invoice_id=state.get("invoice_id", ""),
            )

        return {"approved": True, "decision": "auto_approve",
                "reason": "human_approved",
                "audit": [{"node": "approval", "event": "approved",
                           "by": decision.get("approver"), "note": note}]}

    if action == "reject":
        return {"approved": False, "decision": "reject",
                "reason": "human_rejected",
                "audit": [{"node": "approval", "event": "rejected",
                           "by": decision.get("approver"), "note": note}]}

    # "edit" is not handled here. A correction must re-run matching and policy,
    # which means update_state(as_node="extract") from OUTSIDE the graph -
    # see approve_cli.py. Returning corrected values from this node would
    # write them and then post, skipping the policy check entirely.
    return {"approved": False, "decision": "hold", "reason": "awaiting_correction",
            "audit": [{"node": "approval", "event": "edit_requested"}]}
