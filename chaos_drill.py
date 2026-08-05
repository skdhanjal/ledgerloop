"""Chaos drill. Kill the process mid-run, restart, resume, prove nothing was lost.

Run it twice:
    uv run python chaos_drill.py --phase crash     # dies on purpose
    uv run python chaos_drill.py --phase resume    # picks up the same thread
"""
import argparse
import os
import sys
from pathlib import Path

from rich.console import Console

from graph.build import RECURSION_LIMIT, build_graph
from graph.checkpointing import get_checkpointer, thread_id_for
from graph.context import LedgerContext
from stubs.po_db import PurchaseOrderDB

console = Console()
INVOICE = sorted(Path("data/generated").glob("*.txt"))[0]
THREAD = thread_id_for("acme-corp", "chaos-drill")


def make_graph(explode_on: str | None):
    """Optionally wrap a node so it hard-kills the process, simulating a crash.

    os._exit() skips finally blocks and atexit handlers - a real SIGKILL, not a
    tidy exception. Anything a graceful shutdown would have flushed is lost.
    """
    checkpointer = get_checkpointer("sqlite")
    graph = build_graph(checkpointer=checkpointer)

    if explode_on:
        original = graph.nodes[explode_on].bound

        def suicide(state, *a, **kw):
            console.print(f"[red]*** killing the process inside {explode_on} ***")
            os._exit(137)

        graph.nodes[explode_on].bound = suicide
    return graph


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["crash", "resume"], required=True)
    p.add_argument("--durability", default="sync")
    args = p.parse_args()

    ctx = LedgerContext(tenant_id="acme-corp", po_db=PurchaseOrderDB())
    config = {"configurable": {"thread_id": THREAD},
              "recursion_limit": RECURSION_LIMIT,
              "durability": args.durability}

    if args.phase == "crash":
        graph = make_graph(explode_on="decide")
        graph.invoke({"invoice_path": str(INVOICE)}, context=ctx, config=config)
        sys.exit("unreachable - the node should have killed us")

    graph = make_graph(explode_on=None)
    before = graph.get_state(config)
    console.print(f"[dim]checkpoint found. next={before.next} "
                  f"keys={sorted(before.values)}[/dim]")

    result = graph.invoke(None, context=ctx, config=config)   # None == resume
    console.print(f"[green]resumed and completed:[/green] {result['decision']}")
    console.print("[dim]note: intake and extract did NOT re-run - their "
                  "super-steps were already committed[/dim]")


if __name__ == "__main__":
    main()
