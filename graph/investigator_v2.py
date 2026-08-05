"""The investigator, harness edition. Compare against investigator.py.

Everything that made the hand-built version sixty lines - the agent node, the
ToolNode, should_continue, the cycle, the iteration cap - is either built in
or expressed as middleware.
"""
from langchain.agents import create_agent
from langchain.messages import AIMessage

from .investigator import SYSTEM, opening_message      # reuse both unchanged
from .middleware import ledgerloop_middleware


def build_investigator_v2(model, tools):
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM,               # tenant policy appended by middleware
        middleware=ledgerloop_middleware(),
    )


def investigate_node_factory_v2(model, tools):
    agent = build_investigator_v2(model, tools)

    def investigate(state) -> dict:
        result = agent.invoke({"messages": [opening_message(state)]})
        final: AIMessage = result["messages"][-1]

        tool_calls = sum(len(getattr(m, "tool_calls", []) or [])
                         for m in result["messages"])

        return {
            "investigation": final.content,
            "notes": [f"{tool_calls} tool calls (harness)"],
            "audit": [{"node": "investigate", "event": "investigated",
                       "impl": "create_agent", "tool_calls": tool_calls}],
        }

    return investigate
