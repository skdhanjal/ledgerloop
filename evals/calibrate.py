"""Calibration: label 50 yourself, then measure how much the judge is worth.

Run once before trusting any judge score, and again whenever the judge's
model, rubric or tier changes.
"""
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()
LABELS = Path("evals/human_labels.json")


def cohens_kappa(human: list[int], judge: list[int]) -> float:
    n = len(human)
    observed = sum(h == j for h, j in zip(human, judge)) / n
    labels = set(human) | set(judge)
    expected = sum((human.count(l) / n) * (judge.count(l) / n) for l in labels)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def label_session(items: list[dict]) -> None:
    """Blind labelling: the judge's score is NOT shown while you decide."""
    out = {}
    for i, item in enumerate(items, 1):
        console.rule(f"[bold]{i}/{len(items)}  {item['invoice_id']}")
        console.print(f"[dim]ground truth: {item['seeded_exception']}[/dim]")
        console.print(item["explanation"])
        out[item["invoice_id"]] = int(console.input("\nscore 1-5: "))
    LABELS.write_text(json.dumps(out, indent=2))


def report(human: dict[str, int], judge: dict[str, int]) -> None:
    ids = sorted(set(human) & set(judge))
    h = [human[i] for i in ids]
    j = [round(judge[i]) for i in ids]

    exact = sum(a == b for a, b in zip(h, j)) / len(ids)
    within_one = sum(abs(a - b) <= 1 for a, b in zip(h, j)) / len(ids)
    kappa = cohens_kappa(h, j)
    bias = sum(b - a for a, b in zip(h, j)) / len(ids)

    t = Table(title=f"judge calibration - n={len(ids)}")
    t.add_column("metric"); t.add_column("value"); t.add_column("means")
    t.add_row("exact agreement", f"{exact:.0%}", "same score")
    t.add_row("within +/-1", f"{within_one:.0%}", "close enough to rank")
    t.add_row("Cohen's kappa", f"{kappa:.2f}", verdict(kappa))
    t.add_row("mean bias", f"{bias:+.2f}",
              "judge is more generous" if bias > 0 else "judge is stricter")
    console.print(t)

    console.print("\n[bold]Report this kappa alongside EVERY judge score.[/bold]")
    console.print("[dim]A score without a calibration figure is not a "
                  "measurement.[/dim]")


def verdict(k: float) -> str:
    if k >= 0.8: return "strong - can adjudicate small differences"
    if k >= 0.6: return "moderate - directional only"
    if k >= 0.4: return "weak - triage only, never a ship decision"
    return "no better than chance - do not report"
