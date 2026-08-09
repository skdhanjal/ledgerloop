"""Failure output. The message IS the feature.

"eval failed" gets ignored. A message that names the stratum, shows the
worst example, and links the trace gets fixed the same afternoon.
"""
from evals.gate import GateResult

def render(r: GateResult, current: dict, run_url: str) -> str:
    lines = []

    if r.failures:
        lines.append("GATE FAILED\n")
        for f in r.failures:
            lines.append(f"  x {f}")
        lines.append("")

        # the single most useful thing: a concrete failing case
        worst = current.get("worst_case")
        if worst:
            lines += [
                "  Worst regression:",
                f"    invoice   {worst['invoice_id']}  ({worst['stratum']})",
                f"    expected  {worst['expected']}",
                f"    got       {worst['actual']}",
                f"    trace     {worst['trace_url']}",
                "",
            ]

    for w in r.warnings:
        lines.append(f"  ! {w}")
    for i in r.improvements:
        lines.append(f"  ^ {i}")

    lines += [
        "",
        f"  full report: {run_url}",
        f"  baseline:    evals/baseline.json (updated {current['baseline_date']})",
        "",
        "  If this regression is intentional, update the baseline in the SAME PR",
        "  and explain why in the description. Do not add continue-on-error.",
    ]
    return "\n".join(lines)
