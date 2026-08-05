"""Pipeline vs harness on the same 20 invoices.

Same two corrections as bench_v0.py, and they matter more here because the
whole point of today is a COMPARISON - a broken join makes both columns wrong
in ways that look like a real difference.
"""
import json
import re
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from graph.build import RECURSION_LIMIT, build_graph
from graph.context import LedgerContext
from stubs.po_db import PurchaseOrderDB

console = Console()

TRUTH = {inv["invoice_id"]: inv
         for inv in json.loads(Path("data/generated/invoices.json").read_text())}

RECOMMENDATION = re.compile(r"RECOMMENDATION:\s*(hold|reject|auto_approve)", re.I)


def parse_recommendation(text: str | None) -> str | None:
    if not text:
        return None
    m = RECOMMENDATION.search(text)
    return m.group(1).lower() if m else None


def run(impl: str) -> dict:
    graph = build_graph(investigator=impl)
    po_db = PurchaseOrderDB()
    correct = investigated = agreed = unparsed = 0
    t0 = time.perf_counter()

    for path in sorted(Path("data/generated").glob("*.txt"))[:10]:
        truth = TRUTH[path.stem]              # explicit key join, never index
        ctx = LedgerContext(tenant_id=path.stem.split("_")[0], po_db=po_db)

        result = graph.invoke({"invoice_path": str(path)}, context=ctx,
                              config={"recursion_limit": RECURSION_LIMIT})

        expected = truth["expected_decision"]
        correct += result["decision"] == expected

        # The investigator does not set `decision` - it explains. Score it
        # separately or today's comparison measures the policy function twice.
        investigation = result.get("investigation")
        if investigation:
            investigated += 1
            rec = parse_recommendation(investigation)
            if rec is None:
                unparsed += 1
            elif rec == expected:
                agreed += 1

    return {"impl": impl, "correct": correct, "n": len(TRUTH),
            "investigated": investigated, "agreed": agreed, "unparsed": unparsed,
            "seconds": time.perf_counter() - t0}


if __name__ == "__main__":
    results = [run("handbuilt"), run("harness")]

    t = Table(title="hand-built loop vs create_agent")
    for c in ("implementation", "policy acc", "investigated", "agent agreed",
              "unparsed", "wall clock", "per invoice"):
        t.add_column(c)
    for r in results:
        t.add_row(r["impl"], f"{r['correct']}/{r['n']}", str(r["investigated"]),
                  f"{r['agreed']}/{max(r['investigated'], 1)}", str(r["unparsed"]),
                  f"{r['seconds']:.1f}s", f"{r['seconds'] / r['n']:.1f}s")
    console.print(t)
    console.print("\n[dim]Policy accuracy should be IDENTICAL across both rows - "
                  "the investigator does not touch the decision. The columns that "
                  "can differ are agreement, unparsed answers and time. If policy "
                  "accuracy moved, something other than the investigator changed."
                  "[/dim]")
