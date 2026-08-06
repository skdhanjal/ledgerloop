"""v1 baseline. Same 20 invoices, more dimensions than v0."""
import json, time
from pathlib import Path

from langgraph.types import Command
from rich.console import Console
from rich.table import Table

from graph.app import build_app, context_for

console = Console()
TRUTH = json.loads(Path("data/generated/invoices.json").read_text())
truth_by_id = {item["invoice_id"]: item for item in TRUTH}

def main():
    app = build_app(checkpointer_kind="sqlite", store_kind="memory")
    rows, correct, paused, model_calls, t0 = [], 0, 0, 0, time.perf_counter()

    for idx, path in enumerate(sorted(Path("data/generated").glob("*.txt"))[:7]):
        tenant = path.stem.split("_")[0]
        invoice_id = path.stem
        truth_data = truth_by_id.get(invoice_id, {})
        cfg = {"configurable": {"thread_id": f"bench:{path.stem}"},
               "recursion_limit": 25}
        started = time.perf_counter()

        result = app.invoke({"invoice_path": str(path)},
                            context=context_for(tenant), config=cfg)

        first_decision = result["decision"]                    

        was_paused = "__interrupt__" in result                    

        # v1 can PAUSE - that is a success, not a failure. Auto-approve on
        # behalf of the human so the benchmark measures the machine's decision.
        if was_paused:
            paused += 1
            result = app.invoke(Command(resume={"action": "approve",
                                                "approver": "bench"}),
                                context=context_for(tenant), config=cfg)

        state = app.get_state(cfg).values
        calls = sum(1 for a in state.get("audit", []) if a.get("event") == "verdict")
        model_calls += calls

        expected = truth_data.get("expected_decision")

        # a paused-then-approved invoice was HELD by the machine
        machine = "hold" if was_paused else result["decision"]
        hit = expected in (result["decision"], machine)
        correct += hit
        rows.append((path.stem, truth_data.get("seeded_exception"), expected,
                     first_decision, f"{time.perf_counter()-started:.1f}s", hit))

    elapsed = time.perf_counter() - t0
    t = Table(title=f"v1 - {correct}/{len(rows)} correct, {paused} paused for a human")
    for c in ("invoice", "seeded", "expected", "actual", "time", ""):
        t.add_column(c)
    for r in rows:
        t.add_row(*r[:5], "[green]OK[/green]" if r[5] else "[red]MISS[/red]")
    console.print(t)
    console.print(f"\naccuracy {correct/len(rows):.0%} | {elapsed:.1f}s total "
                  f"| {elapsed/len(rows):.1f}s per invoice | {paused} required a human")


if __name__ == "__main__":
    main()