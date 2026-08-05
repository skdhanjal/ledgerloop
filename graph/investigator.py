"""The Exception Investigator: a hand-built ReAct loop. No prebuilt agent.

You will replace this with one call to create_agent on Day 7 and compare the
two on tokens, latency and accuracy. Writing it by hand first is the point -
this is the loop every framework wraps.
"""
import operator
from typing import Annotated, Literal, TypedDict

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

MAX_TOOL_ITERATIONS = 8          # semantic brake (see Day 5)

SYSTEM = """You are an accounts-payable exception investigator.

An automated policy check has flagged an invoice. Your job is to establish the
ROOT CAUSE using the tools, then state a recommendation.

Rules:
- Verify claims with tools. Do not assume what a purchase order says.
- A quantity mismatch may be a unit-of-measure difference (cases vs units).
  Check the amounts before concluding a shortfall.
- Be brief. When you have enough evidence, stop calling tools and answer with:
  ROOT CAUSE: <one line>
  EVIDENCE: <tool findings you relied on>
  RECOMMENDATION: <hold | reject | auto_approve> - <why>"""


class InvestigatorState(TypedDict):
    messages: Annotated[list, add_messages]
    tool_calls_made: Annotated[int, operator.add]


def build_investigator(model, tools):
    model_with_tools = model.bind_tools(tools)

    def agent(state: InvestigatorState) -> dict:
        response = model_with_tools.invoke(state["messages"])
        n = len(getattr(response, "tool_calls", []) or [])
        return {"messages": [response], "tool_calls_made": n}

    def should_continue(state: InvestigatorState) -> Literal["tools", "__end__"]:
        last = state["messages"][-1]

        # semantic brake first: a real answer beats an exception
        if state.get("tool_calls_made", 0) >= MAX_TOOL_ITERATIONS:
            return END

        return "tools" if getattr(last, "tool_calls", None) else END

    b = StateGraph(InvestigatorState)
    b.add_node("agent", agent)
    b.add_node("tools", ToolNode(tools))
    b.add_edge(START, "agent")
    b.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    b.add_edge("tools", "agent")            # the cycle
    return b.compile()


def opening_message(state) -> HumanMessage:
    """What the investigator is told about the flagged invoice."""
    codes = ", ".join(e["code"] for e in state.get("exceptions", [])) or "unknown"
    return HumanMessage(
        f"Invoice {state.get('invoice_id')} was flagged: {codes}.\n"
        f"Vendor: {state.get('vendor')}\n"
        f"Invoice number: {state.get('invoice_no')}\n"
        f"PO reference: {state.get('po_number')}\n"
        f"Invoice total: {state.get('total')}\n\n"
        f"Investigate and report."
    )


def investigate_node_factory(model, tools):
    """Wraps the agent graph as a single node in the main graph.

    Day 13 replaces this manual invoke with a proper subgraph mount.
    """
    agent_graph = build_investigator(model, tools)

    def investigate(state) -> dict:
        result = agent_graph.invoke({
            "messages": [SystemMessage(SYSTEM), opening_message(state)],
            "tool_calls_made": 0,
        })
        final: AIMessage = result["messages"][-1]
        return {
            "investigation": final.content,
            "notes": [f"{result['tool_calls_made']} tool calls"],
            "audit": [{"node": "investigate", "event": "investigated", "tool_calls": result["tool_calls_made"]}],
        }

    return investigate
