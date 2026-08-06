"""Time travel: rewind a wrongly-held invoice and re-drive it."""
from pathlib import Path

from rich.console import Console

from graph.build import build_graph
from graph.checkpointing import get_checkpointer, thread_id_for
from graph.context import LedgerContext
from stubs.po_db import PurchaseOrderDB

console = Console()
graph = build_graph(checkpointer=get_checkpointer("sqlite"))
po_db = PurchaseOrderDB()

invoice = sorted(Path("data/generated").glob("*.txt"))[3]
thread = thread_id_for("acme-corp", invoice.stem)
config = {"configurable": {"thread_id": thread}}

# --- original run: strict tolerance, invoice gets held ---
strict = LedgerContext(tenant_id="acme-corp", po_db=po_db, variance_tolerance=0.02)
first = graph.invoke({"invoice_path": str(invoice)}, context=strict, config=config)
console.print(f"original  -> {first['decision']} ({first['reason']})")

console.rule("[bold]history")
target = None
for snap in graph.get_state_history(config):
    console.print(f"  step {snap.metadata.get('step'):>2}  next={str(snap.next):<16} "
                  f"id={snap.config['configurable']['checkpoint_id'][:8]}")
    if snap.next == ("decide",):
        target = snap.config          # the checkpoint BEFORE the policy ran

# --- fork: same state, different policy ---
console.rule("[bold]fork with a looser tolerance")
lenient = LedgerContext(tenant_id="acme-corp", po_db=po_db, variance_tolerance=0.40)
second = graph.invoke(None, context=lenient, config=target)
console.print(f"forked    -> {second['decision']} ({second['reason']})")

console.rule("[bold]both branches still exist")
console.print(f"history length: {len(list(graph.get_state_history(config)))} checkpoints")
console.print("[dim]the original run was not overwritten - forking appends a "
              "new branch from the chosen checkpoint[/dim]")
