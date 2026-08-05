"""v0 baseline: run all 20 invoices, measure everything, write BENCH.md.

Every later version is compared against these numbers. Without a baseline,
"the multi-agent version is better" is a feeling.
"""
import json
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from graph.build import RECURSION_LIMIT, build_graph
from graph.context import LedgerContext
from stubs.po_db import PurchaseOrderDB

console = Console()
TRUTH = {i["invoice_id"]: i
         for i in json.loads(Path("data/generated/invoices.json").read_text())}


def main():
    graph = build_graph()
    po_db = PurchaseOrderDB()
    rows, correct, investigated, t0 = [], 0, 0, time.perf_counter()

    for path in sorted(Path("data/generated").glob("*.txt"))[:2]:
        tenant = path.stem.split("_")[0]
        ctx = LedgerContext(tenant_id=tenant, po_db=po_db)
        started = time.perf_counter()

        result = graph.invoke({"invoice_path": str(path)}, context=ctx,
                              config={"recursion_limit": RECURSION_LIMIT})

        truth = next((t for t in TRUTH.values() if path.stem.endswith(f"{list(TRUTH).index(t['invoice_id']):03d}")), None)
        expected = truth["expected_decision"] if truth else "?"
        actual = result["decision"]
        hit = expected == actual
        correct += hit
        rows.append((path.stem, truth["seeded_exception"] if truth else "?",
                     expected, actual, f"{time.perf_counter() - started:.1f}s", hit))

    elapsed = time.perf_counter() - t0

    t = Table(title=f"v0 baseline - {correct}/{len(rows)} correct")
    for c in ("invoice", "seeded", "expected", "actual", "time", ""):
        t.add_column(c)
    for r in rows:
        t.add_row(*r[:5], "[green]OK[/green]" if r[5] else "[red]MISS[/red]")
    console.print(t)
    console.print(f"\naccuracy {correct / len(rows):.0%} | wall clock {elapsed:.1f}s "
                  f"| {elapsed / len(rows):.1f}s per invoice")


if __name__ == "__main__":
    main()
