"""Run one invoice on a durable thread, then inspect what was written."""
from pathlib import Path

from rich.console import Console
from rich.json import JSON

from graph.build import RECURSION_LIMIT, build_graph
from graph.checkpointing import get_checkpointer, thread_id_for
from graph.context import LedgerContext
from graph.store import get_store
from stubs.po_db import PurchaseOrderDB

console = Console()
checkpointer = get_checkpointer("postgres")
store = get_store("memory")
graph = build_graph(checkpointer=checkpointer, store=store)

invoice = sorted(Path("data/generated").glob("acme-corp_*.txt"))[4]
thread = thread_id_for("acme-corp", invoice.stem)
config = {"configurable": {"thread_id": thread}, "recursion_limit": RECURSION_LIMIT}
ctx = LedgerContext(tenant_id="acme-corp", po_db=PurchaseOrderDB())

console.rule(f"[bold]run - thread {thread}")
result = graph.invoke({"invoice_path": str(invoice)}, context=ctx, config=config)
console.print(JSON.from_data(result))

console.rule("[bold]the checkpoint that survived")
snapshot = graph.get_state(config)
console.print(f"next        : {snapshot.next}")
console.print(f"checkpoint  : {snapshot.config['configurable']['checkpoint_id']}")
console.print(f"state keys  : {sorted(snapshot.values)}")
console.print(f"step        : {snapshot.metadata.get('step')}")

console.rule("[bold]full history (newest first)")
for snap in graph.get_state_history(config):
    wrote = ", ".join(sorted(snap.metadata.get("writes") or {})) or "-"
    console.print(f"  step {snap.metadata.get('step'):>2}  next={str(snap.next):<18} wrote: {wrote}")

console.rule("[bold]resume a finished thread")
# Passing None means "continue from the checkpoint", not "start again".
# A completed thread has next == () so this is a no-op - which is itself
# the proof that resumption is checkpoint-driven, not input-driven.
again = graph.invoke(None, context=ctx, config=config)
console.print(f"decision unchanged: {again['decision']}")
