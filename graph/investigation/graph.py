"""The investigation subgraph. Compiled once, mounted as a node."""
from langchain.agents import create_agent
from langgraph.graph import END, START, StateGraph

from ..extraction import ExceptionVerdict
from ..investigator import SYSTEM
from ..middleware import ledgerloop_middleware
from .state import InvestigationState

def _opening(state: InvestigationState) -> str:
    known = ("\n".join(f"- {k}" for k in state.get("prior_knowledge", []))
             or "No prior history with this vendor.")
    return (
        f"Flagged: {', '.join(state.get('exception_codes', [])) or 'unknown'}\n"
        f"Vendor: {state.get('vendor')}\n"
        f"PO reference: {state.get('po_number')}\n"
        f"Invoice total: {state.get('total')}\n\n"
        f"What we know about this vendor:\n{known}\n\nInvestigate and report."
    )


def build_investigation_graph(model, tools):
    """A one-node graph today. That is deliberate.

    The node is a create_agent instance, so this looks like overhead - and it
    is, until Day 17 adds a critique loop and Day 16 adds a peer handoff. The
    boundary is what makes those additions local changes rather than surgery
    on the payment pipeline.
    """
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM,
        response_format=ExceptionVerdict,
        middleware=ledgerloop_middleware(model),
    )

    def investigate(state: InvestigationState) -> dict:
        result = agent.invoke({"messages": [{"role": "user", "content": _opening(state)}]})
        verdict = result.get("structured_response")
        calls = sum(len(getattr(m, "tool_calls", []) or [])
                    for m in result["messages"])
        return {
            "messages": result["messages"],
            "verdict": verdict.model_dump() if verdict else None,
            "tool_calls_made": calls,
        }

    b = StateGraph(InvestigationState)
    b.add_node("investigate", investigate)
    b.add_edge(START, "investigate")
    b.add_edge("investigate", END)
    return b.compile()
