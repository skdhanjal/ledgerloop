"""Middleware that records what ACTUALLY served each call.

Providers rotate models behind stable aliases. Without this, a silent upgrade
is indistinguishable from your own regression - and that is a day of bisecting
prompts that were never the problem.
"""
from langchain.agents.middleware import after_model


@after_model
def record_served_model(state, runtime):
    """Capture the concrete model id from the response metadata."""
    last = state["messages"][-1]
    meta = getattr(last, "response_metadata", {}) or {}
    served = meta.get("model_name") or meta.get("model") or "unknown"

    usage = getattr(last, "usage_metadata", None) or {}

    return {"audit": [{
        "node": "model_call",
        "event": "served",
        "model_served": served,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
    }]}
