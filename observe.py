"""Observe a run with and without subgraph visibility. Run this FIRST -
before you need it to debug something at 11pm.
"""
from pathlib import Path

from rich.console import Console

from graph.app import build_app, context_for

console = Console()
app = build_app(checkpointer_kind="sqlite", store_kind="memory")
invoice = sorted(Path("data/generated").glob("*.txt"))[4]
cfg = {"configurable": {"thread_id": "obs:1"}, "recursion_limit": 25}
ctx = context_for("acme-corp", variance_tolerance=0.0)     # force an exception

console.rule("[bold]default - parent super-steps only")
for update in app.stream({"invoice_path": str(invoice)}, context=ctx,
                         config=cfg, stream_mode="updates"):
    for node, delta in update.items():
        console.print(f"  {node}: {sorted(delta)}")

console.rule("[bold]subgraphs=True - the investigation opens up")
cfg2 = {**cfg, "configurable": {"thread_id": "obs:2"}}
for ns, update in app.stream({"invoice_path": str(invoice)}, context=ctx,
                             config=cfg2, stream_mode="updates", subgraphs=True):
    indent = "  " * (len(ns) + 1)
    label = f"[dim]{ns[-1].split(':')[0]}[/dim] " if ns else ""
    for node, delta in update.items():
        keys = sorted(delta) if isinstance(delta, (dict, list, set)) else delta
        console.print(f"{indent}{label}{node}: {keys}")

console.rule("[bold]nested state")
snap = app.get_state(cfg2, subgraphs=True)
console.print(f"parent next={snap.next}  keys={len(snap.values)}")
# 2. Inspect the parent state values/keys
# console.print(f"Parent State Keys: {sorted(snap.values.keys())}")
# console.print(f"Parent State Data: {snap.values}")

for task in snap.tasks:
    console.print(f"Pending Task Node: {task.name}")
    # Check if this task is paused on an interrupt
    if task.interrupts:
        for interrupt in task.interrupts:
            console.print(f"  Interrupt Value: {interrupt.value}")
