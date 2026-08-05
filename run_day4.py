"""Run one invoice with injected dependencies and a scoped output."""
from pathlib import Path

from rich.console import Console
from rich.json import JSON

from graph.build import build_graph
from graph.context import LedgerContext
from stubs.po_db import PurchaseOrderDB

console = Console()

graph = build_graph()

invoice = sorted(Path("data/generated").glob("acme-corp_*.txt"))[0]

ctx = LedgerContext(
    tenant_id="acme-corp",
    po_db=PurchaseOrderDB(),        # constructed ONCE, injected - never in state
    variance_tolerance=0.05,
)

result = graph.invoke(
    {"invoice_path": str(invoice)},
    context=ctx,
    config={"configurable": {"thread_id": f"acme-corp:{invoice.stem}"}},
)

console.rule("[bold]what the caller receives")
console.print(JSON.from_data(result))
console.print(f"\n[dim]keys returned: {sorted(result)}[/dim]")
console.print("[dim]raw_text present? "
              f"{'raw_text' in result}  <- output_schema keeps it internal[/dim]")

graph.get_graph().draw_mermaid_png(output_file_path="graph.png")

