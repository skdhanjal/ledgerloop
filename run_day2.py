"""Run one invoice through the graph and show what actually happened."""

from pathlib import Path
from rich.console import Console
from rich.json import JSON

from graph.build import build_graph

console = Console()
graph = build_graph()

invoice = sorted(Path("data/generated").glob("*.txt"))[0]

console.rule("[bold]per-node updates (stream_mode='updates')")
for chunk in graph.stream({"invoice_path": str(invoice)}, stream_mode="updates"):
    for node_name, delta in chunk.items():
        keys = ", ".join(delta.keys()) if delta else "(nothing)"
        console.print(f"  [teal]{node_name:<9}[/teal] wrote: {keys}")

console.rule("[bold]final state (what invoke returns)")

final = graph.invoke({"invoice_path": str(invoice)})
compact = {k: (v[:60] + "..." if isinstance(v, str) and len(v) > 60 else v)
           for k, v in final.items()}
           
console.print(JSON.from_data(compact))

console.rule("[bold]topology")
print(graph.get_graph().draw_mermaid())
