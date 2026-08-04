"""Reproduce InvalidUpdateError, then fix it. Run this, read the traceback, keep it.

This is the failure you will hit for real on Day 14. Meeting it now, in nine
lines with no model involved, is far cheaper than meeting it inside a fan-out.
"""
import operator
from typing import Annotated, TypedDict

from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph


def run(state_cls, label):
    def writer_a(state):
        return {"findings": ["from A"]}

    def writer_b(state):
        return {"findings": ["from B"]}

    b = StateGraph(state_cls)
    b.add_node("a", writer_a)
    b.add_node("b", writer_b)
    b.add_edge(START, "a")        # both edges leave START, so a and b run
    b.add_edge(START, "b")        # in the SAME super-step
    b.add_edge("a", END)
    b.add_edge("b", END)
    graph = b.compile()

    try:
        print(f"{label:<12} ->", graph.invoke({}))
    except InvalidUpdateError as e:
        print(f"{label:<12} -> InvalidUpdateError: {str(e)[:90]}...")


class Broken(TypedDict, total=False):
    findings: list[str]                              # no reducer


class Fixed(TypedDict, total=False):
    findings: Annotated[list[str], operator.add]     # reducer


if __name__ == "__main__":
    run(Broken, "no reducer")
    run(Fixed, "operator.add")
