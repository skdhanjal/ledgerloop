"""Middleware tests. Deterministic, no API key - the FakeModel from Day 6 again."""
from dataclasses import dataclass

from langchain.messages import AIMessage, ToolMessage

from graph.middleware import MAX_MODEL_CALLS, SECRET_PATTERNS, redact_tool_output


@dataclass
class FakeRequest:
    tool_call_id: str = "c1"


def test_account_number_is_redacted_before_reaching_messages():
    def handler(_):
        return ToolMessage(content="Vendor account 123456789012 at HDFC0001234",
                           tool_call_id="c1")

    out = redact_tool_output(FakeRequest(), handler)
    assert "123456789012" not in out.content
    assert "[ACCOUNT_REDACTED]" in out.content
    assert "[IFSC_REDACTED]" in out.content


def test_redaction_leaves_legitimate_data_intact():
    """A PO number and a price must survive - over-redaction breaks the agent."""
    def handler(_):
        return ToolMessage(content="PO PO-4002 line SKU-2291 unit_price=85.00",
                           tool_call_id="c1")

    out = redact_tool_output(FakeRequest(), handler)
    assert "PO-4002" in out.content and "85.00" in out.content


def test_redaction_is_applied_to_every_call_not_just_the_first():
    def handler(_):
        return ToolMessage(content="acct 999888777666", tool_call_id="c1")

    for _ in range(3):
        assert "999888777666" not in redact_tool_output(FakeRequest(), handler).content


def test_call_limit_is_below_the_free_tier_danger_zone():
    """A guard on the guard: this constant protects your daily quota."""
    assert 1 <= MAX_MODEL_CALLS <= 10


def test_patterns_compile_and_have_replacements():
    for pattern, replacement in SECRET_PATTERNS:
        assert pattern.pattern and replacement.startswith("[")
