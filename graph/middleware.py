"""Middleware stack, now with summarization.

ORDERING (outermost first) - unchanged reasoning from Day 7:
  1. redact_tool_output      guardrail: nothing inside it may leak
  2. model_call_limit        budget: must not count retries below it
  3. summarize_history       context management: closest to the model
  4. tenant_policy_prompt    prompt assembly, innermost

Summarization sits INSIDE redaction deliberately. Reverse them and you
summarise unredacted tool output, then store the secrets inside the summary -
where they are no longer pattern-matchable and will be re-sent forever.
"""

import re
from langchain.agents.middleware import (ModelCallLimitMiddleware, ModelRequest, PIIMiddleware, SummarizationMiddleware,
                                         dynamic_prompt, wrap_tool_call)

from .guardrails import enforce_tool_policy                                         

MAX_MODEL_CALLS = 8          # free-tier quota protection; see Day 5's two brakes

SUMMARY_THRESHOLD_TOKENS = 12_000

SUMMARY_INSTRUCTION = """Summarise the investigation so far for an
accounts-payable reviewer.

PRESERVE EXACTLY: every figure (prices, quantities, totals), every PO and
invoice number, and which tool produced each finding. A summary that says
"a price discrepancy was found" without the two numbers is useless here.

Drop: reasoning that led nowhere, repeated lookups, pleasantries."""

# bank details and tax ids that must never enter the message channel
SECRET_PATTERNS = [
    (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), "[IFSC_REDACTED]"),
    (re.compile(r"\b\d{9,18}\b"), "[ACCOUNT_REDACTED]"),
    (re.compile(r"\b[0-9A-Z]{15}\b"), "[GSTIN_REDACTED]"),
]

TENANT_POLICY = {
    "acme-corp": "Acme requires a PO for every invoice above 10,000. "
                 "Short shipments are always held, never partially approved.",
    "globex-ltd": "Globex tolerates no price variance. Any deviation from the "
                  "purchase order price is an exception worth reporting.",
}


@wrap_tool_call
def redact_tool_output(request, handler):
    """Scrub secrets from tool results BEFORE they enter the message channel.

    Outermost on purpose: once an unredacted string is in `messages` it is
    checkpointed, re-sent on every later turn, and streamed to a browser on
    Day 20. Redacting later is too late.
    """
    result = handler(request)
    content = getattr(result, "content", None)
    if isinstance(content, str):
        for pattern, replacement in SECRET_PATTERNS:
            content = pattern.sub(replacement, content)
        result.content = content
    return result


@dynamic_prompt
def tenant_policy_prompt(request: ModelRequest) -> str:
    """Append this tenant's AP policy to the system prompt.

    Same compiled agent, different instructions per client - no redeploy.
    On Day 10 this text comes from the Store instead of a dict.
    """
    from .investigator import SYSTEM          # local import avoids a cycle

    tenant = getattr(request.runtime.context, "tenant_id", None)
    policy = TENANT_POLICY.get(tenant)
    if not policy:
        return SYSTEM
    return f"{SYSTEM}\n\nTENANT POLICY ({tenant}):\n{policy}"


def ledgerloop_middleware(model):
    """The stack, in order. Index 0 is outermost."""
    return [
        enforce_tool_policy,
        redact_tool_output,
        PIIMiddleware("email", strategy="redact"),
        PIIMiddleware("credit_card", strategy="block"),
        ModelCallLimitMiddleware(thread_limit=MAX_MODEL_CALLS),
        SummarizationMiddleware(
            model=model,
            max_tokens_before_summary=SUMMARY_THRESHOLD_TOKENS,
            summary_prompt=SUMMARY_INSTRUCTION,
        ),
        tenant_policy_prompt,
    ]
