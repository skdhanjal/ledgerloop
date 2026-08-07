"""The test that proves defer works: uneven branches in one graph."""
from typing import Annotated, TypedDict

import operator
from langgraph.graph import END, START, StateGraph


class S(TypedDict, total=False):
    results: Annotated[list, operator.add]
    joins: Annotated[list, operator.add]


def build(defer: bool):
    def fast(state):
        return {"results": ["fast"]}

    def slow_a(state):
        return {"results": ["slow_a"]}

    def slow_b(state):                       # second hop - one step deeper
        return {"results": ["slow_b"]}

    def join(state):
        # records what it could see EACH time it ran
        return {"joins": [len(state.get("results", []))]}

    b = StateGraph(S)
    b.add_node("fast", fast)
    b.add_node("slow_a", slow_a)
    b.add_node("slow_b", slow_b)
    b.add_node("join", join, defer=defer)

    b.add_edge(START, "fast")
    b.add_edge(START, "slow_a")
    b.add_edge("slow_a", "slow_b")           # deeper branch
    b.add_edge("fast", "join")
    b.add_edge("slow_b", "join")
    b.add_edge("join", END)
    return b.compile()


def test_without_defer_the_join_runs_early_and_twice():
    out = build(defer=False).invoke({})
    assert len(out["joins"]) > 1             # ran more than once
    assert min(out["joins"]) < 3             # saw partial data


def test_with_defer_the_join_runs_once_with_everything():
    out = build(defer=True).invoke({})
    assert out["joins"] == [3]               # exactly once, all three results
