"""The money test, end to end. Kill between approved and posted.

Run:
    uv run python money_test.py --phase crash
    uv run python money_test.py --phase resume
    curl http://localhost:8000/_debug/payments      # must show count: 1
"""
import argparse
import os

from langgraph.types import Command
from rich.console import Console

from graph.app import build_app, context_for

console = Console()
THREAD = "acme-corp:money-test"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["crash", "resume"], required=True)
    args = p.parse_args()

    app = build_app(checkpointer_kind="sqlite", store_kind="memory")
    cfg = {"configurable": {"thread_id": THREAD}, "durability": "sync"}
    ctx = context_for("acme-corp")

    if args.phase == "crash":
        # run to the approval gate, approve, then die INSIDE post_to_erp
        # after the ERP write has landed but before the step commits
        app.invoke({"invoice_path": "data/generated/acme-corp_000.txt"}, context=ctx, config=cfg)

        original = app.nodes["post"].runnable

        def post_then_die(state, runtime):
            result = original(state, runtime)          # the ERP write LANDS
            console.print("[red]*** killed after the ERP write, "
                          "before the checkpoint commit ***")
            os._exit(137)

        app.nodes["post"].runnable = post_then_die
        app.invoke(Command(resume={"action": "approve", "approver": "test"}), context=ctx, config=cfg)
        return

    console.print("[dim]resuming - post will re-run from the top[/dim]")
    result = app.invoke(None, context=ctx, config=cfg)
    console.print(f"[green]resumed:[/green] payment_id={result.get('payment_id')}")
    console.print("[bold]now check /_debug/payments - count MUST be 1[/bold]")


if __name__ == "__main__":
    main()
