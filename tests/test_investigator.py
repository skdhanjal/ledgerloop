"""Test an agent WITHOUT calling a model - by scripting the model itself."""
from langchain.messages import AIMessage

from graph.investigator import MAX_TOOL_ITERATIONS, build_investigator
from graph.tools import make_tools


class FakeModel:
    """Returns a scripted sequence of responses. bind_tools is a no-op."""

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        msg = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return msg


class FakePoDB:
    def get_po(self, n):
        return None if n == "PO-99017" else {
            "po_number": n, "vendor": "Kestrel",
            "lines": [{"sku": "SKU-1", "quantity": 10, "unit_price": 5.0}]}

    def get_receipt(self, n):
        return {"po_number": n, "lines": [{"sku": "SKU-1", "quantity_received": 10}]}


def tool_call(name, args, cid="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


TOOLS = make_tools(FakePoDB(), {"Kestrel": [{"invoice_no": "INV-1", "date": "2026-01-01"}]})


def test_loop_stops_when_model_stops_calling_tools():
    model = FakeModel([tool_call("lookup_po", {"po_number": "PO-4001"}),
                       AIMessage("ROOT CAUSE: none found")])
    g = build_investigator(model, TOOLS)
    out = g.invoke({"messages": [], "tool_calls_made": 0})
    assert "ROOT CAUSE" in out["messages"][-1].content


def test_tool_result_is_fed_back_to_the_model():
    model = FakeModel([tool_call("lookup_po", {"po_number": "PO-99017"}),
                       AIMessage("ROOT CAUSE: PO does not exist")])
    g = build_investigator(model, TOOLS)
    out = g.invoke({"messages": [], "tool_calls_made": 0})
    tool_msgs = [m for m in out["messages"] if m.type == "tool"]
    assert tool_msgs and "NOT_FOUND" in tool_msgs[0].content


def test_semantic_brake_stops_a_model_that_never_finishes():
    """The failure mode that matters: a model looping forever on tool calls."""
    model = FakeModel([tool_call("lookup_po", {"po_number": "PO-4001"})])  # always
    g = build_investigator(model, TOOLS)
    out = g.invoke({"messages": [], "tool_calls_made": 0},
                   config={"recursion_limit": 50})
    assert out["tool_calls_made"] >= MAX_TOOL_ITERATIONS
    assert out["tool_calls_made"] <= MAX_TOOL_ITERATIONS + 1


# ---- tools as plain functions -----------------------------------------
def test_missing_po_returns_not_found_rather_than_raising():
    lookup_po = next(t for t in TOOLS if t.name == "lookup_po")
    assert "NOT_FOUND" in lookup_po.invoke({"po_number": "PO-99017"})


def test_duplicate_detection():
    check = next(t for t in TOOLS if t.name == "check_duplicate_invoice")
    assert "DUPLICATE" in check.invoke({"vendor": "Kestrel", "invoice_no": "INV-1"})
    assert "UNIQUE" in check.invoke({"vendor": "Kestrel", "invoice_no": "INV-9"})


def test_tool_output_is_truncated():
    lookup_po = next(t for t in TOOLS if t.name == "lookup_po")
    assert len(lookup_po.invoke({"po_number": "PO-4001"})) <= 600
