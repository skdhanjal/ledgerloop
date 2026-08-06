"""Operator CLI: list paused invoices, show the payload, resume them.

This is the runbook. Someone will use it at 2am on a live payment, so it
prints what it is about to do and requires the thread id explicitly.
"""
import argparse
import json

from langgraph.types import Command
from rich.console import Console
from rich.json import JSON

from graph.build import build_graph
from graph.checkpointing import get_checkpointer
from graph.context import LedgerContext
from graph.routers import route_after_investigate
from stubs.po_db import PurchaseOrderDB

console = Console()


def session():
    cp = get_checkpointer("postgres")
    graph = build_graph(checkpointer=cp)
    ctx = LedgerContext(tenant_id="acme-corp", po_db=PurchaseOrderDB())
    return graph, ctx


def show(graph, config):
    snap = graph.get_state(config)
    if not snap.next:
        console.print("[dim]thread is complete - nothing to approve[/dim]")
        return None

    # A paused thread has pending interrupts on its tasks.
    for task in snap.tasks:
        for intr in (task.interrupts or []):
            console.rule(f"[bold]awaiting approval - {config['configurable']['thread_id']}")
            console.print(JSON.from_data(intr.value))
            return intr.value
    console.print(f"[dim]not paused; next = {snap.next}[/dim]")
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("thread")
    p.add_argument("--action", choices=["show", "approve", "reject", "edit"],
                   default="show")
    p.add_argument("--approver", default="ops@example.com")
    p.add_argument("--note", default="")
    p.add_argument("--set", action="append", default=[],
                   help="field=value, for --action edit")
    args = p.parse_args()

    graph, ctx = session()
    config = {"configurable": {"thread_id": args.thread}}

    if args.action == "show":
        show(graph, config)
        return

    if args.action == "edit":
        values = {}
        for pair in args.set:
            k, v = pair.split("=", 1)
            values[k] = float(v) if k in {"total"} else v

        console.print(f"[yellow]writing {values} as_node='extract'[/yellow]")
        # as_node="extract" is the load-bearing part: it makes LangGraph believe
        # extraction produced these values, so matching and the POLICY CHECK
        # run again against the human's numbers. Writing it as_node="decide"
        # would skip policy entirely.
        graph.update_state(config, values, as_node="extract")
        result = graph.invoke(None, context=ctx, config=config)
        console.print(f"re-evaluated -> {result['decision']} ({result['reason']})")
        return

    payload = {"action": args.action, "approver": args.approver, "note": args.note}
    console.print(f"[yellow]resuming with {json.dumps(payload)}[/yellow]")
    result = graph.invoke(Command(resume=payload), context=ctx, config=config)
    console.print(f"[green]completed -> {result['decision']}[/green]")


if __name__ == "__main__":
    main()
