"""LedgerLoop middleware.

ORDERING (outermost first) - do not shuffle without reading this:
  1. redact_tool_output   guardrail: secrets must never reach the model, so it
                          wraps everything inside it
  2. model_call_limit     budget: counts real model calls, and must not count
                          retries performed by layers beneath it
  3. tenant_policy_prompt context: injects per-tenant rules closest to the call

Rule of thumb: guardrails outermost, context management innermost.
"""
import re

from langchain.agents.middleware import (ModelCallLimitMiddleware, ModelRequest,
                                         dynamic_prompt, wrap_tool_call)

MAX_MODEL_CALLS = 8          # free-tier quota protection; see Day 5's two brakes

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


def ledgerloop_middleware():
    """The stack, in order. Index 0 is outermost."""
    return [
        redact_tool_output,
        ModelCallLimitMiddleware(thread_limit=MAX_MODEL_CALLS),
        tenant_policy_prompt,
    ]
