"""The gate: compare a run against a pinned baseline, per stratum, with a band.

Design rules, in priority order:
  1. Never fail on noise. The band comes from the MEASURED detection floor
     (Exercise 22.3), not from optimism.
  2. Fail loudly and specifically. A failure message that says "eval failed"
     gets ignored; one that names the stratum and links the trace gets fixed.
  3. Report improvements too - a jump can mean a broken evaluator.
"""
import argparse
import json
import os
import sys
from pathlib import Path

BASELINE = Path("evals/baseline.json")   # pinned in Build 22.4

# From Exercise 22.3: the smallest regression this suite reliably detects.
# If you have not measured yours, do that before setting these.
NOISE_FLOOR_PP = 3.0
BAND_PP = NOISE_FLOOR_PP * 1.5        # fail only clearly outside the noise

# Hard gates: no band, no tolerance, no discussion.
HARD_METRICS = {
    "double_pay_incidents": 0,
    "pii_events_leaked": 0,
    "unserializable_state": 0,
    "cross_tenant_reads": 0,
}


class GateResult:
    def __init__(self):
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.improvements: list[str] = []

    @property
    def passed(self) -> bool:
        return not self.failures


def check(current: dict, baseline: dict | None = None) -> GateResult:
    if baseline is None:
        if not BASELINE.exists():
            raise SystemExit(
                f"No {BASELINE}. Pin one first (Build 22.4):\n"
                "  uv run python -m evals.run_eval --split dev --model local "
                "--json out.json\n"
                "  uv run python -m evals.gate --current out.json --update-baseline")
        baseline = json.loads(BASELINE.read_text())
    r = GateResult()

    # --- hard gates ---
    for metric, allowed in HARD_METRICS.items():
        actual = current.get(metric, 0)
        if actual > allowed:
            r.failures.append(
                f"HARD GATE: {metric} = {actual} (must be {allowed}). "
                f"This failure class is silent in production - see BENCH.md.")

    # --- soft gates, aggregate ---
    for metric in ("decision_accuracy", "extraction_match", "exception_recall"):
        cur, base = current[metric] * 100, baseline[metric] * 100
        delta = cur - base

        if delta < -BAND_PP:
            r.failures.append(
                f"{metric}: {cur:.1f}% vs baseline {base:.1f}% "
                f"({delta:+.1f}pp, band +/-{BAND_PP:.1f}pp)")
        elif delta < -NOISE_FLOOR_PP:
            r.warnings.append(
                f"{metric}: {delta:+.1f}pp - inside the band but worth a look")
        elif delta > BAND_PP:
            # An unexplained jump usually means a broken evaluator, not genius
            r.improvements.append(
                f"{metric}: {delta:+.1f}pp - verify the evaluator still works")

    # --- soft gates, per stratum: where an aggregate hides a real break ---
    for stratum, base_score in baseline["by_stratum"].items():
        cur_score = current["by_stratum"].get(stratum)
        if cur_score is None:
            r.failures.append(f"stratum '{stratum}' missing - dataset changed?")
            continue

        delta = (cur_score - base_score) * 100
        # a whole stratum collapsing can hide inside a 2pp aggregate move
        if delta < -15:
            r.failures.append(
                f"stratum '{stratum}': {cur_score:.0%} vs {base_score:.0%} "
                f"({delta:+.0f}pp) - a specific capability broke")

    # --- judge scores are advisory unless calibration is strong ---
    if current.get("judge_kappa", 0) < 0.6:
        r.warnings.append(
            f"judge kappa {current.get('judge_kappa', 0):.2f} - explanation "
            f"scores are NOT gate-eligible below 0.6, reporting only")
    elif "judge_mean" in current:
        delta = current["judge_mean"] - baseline["judge_mean"]
        if delta < -0.5:
            r.failures.append(
                f"explanation quality {current['judge_mean']:.2f} vs "
                f"{baseline['judge_mean']:.2f} (kappa {current['judge_kappa']:.2f})")

    return r

def update_baseline(current: dict) -> None:
    """Re-pin, and print the diff you are about to commit.

    Deliberately noisy. Re-pinning is a decision, so the diff belongs in
    the PR body where a reviewer sees it - see docs/BASELINE.md."""
    if BASELINE.exists():
        old = json.loads(BASELINE.read_text())
        for m in ("decision_accuracy", "extraction_match",
                  "exception_recall"):
            delta = (current[m] - old[m]) * 100
            print(f"  {m}: {old[m]:.1%} -> {current[m]:.1%} ({delta:+.1f}pp)")
        for k, v in current["by_stratum"].items():
            base = old["by_stratum"].get(k)
            if base is None:
                print(f"  stratum {k}: NEW")
            elif abs(v - base) >= 0.05:
                print(f"  stratum {k}: {base:.0%} -> {v:.0%}")
    else:
        # First pin. Nothing to compare against, so nothing is gated -
        # say so out loud rather than reporting a silent pass.
        print("No previous baseline - creating the first pin. Nothing gated.")
    BASELINE.write_text(json.dumps(current, indent=2))
    print(f"\nWrote {BASELINE}. Commit it in THIS PR, and say why.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", required=True,
                    help="metrics JSON from run_eval --json")
    ap.add_argument("--update-baseline", action="store_true",
                    dest="update")
    ap.add_argument("--report", action="store_true",
                    help="render the full message even on pass")
    a = ap.parse_args()
    current = json.loads(Path(a.current).read_text())

    if a.update:
        update_baseline(current)
        raise SystemExit(0)

    result = check(current)
    if a.report or not result.passed:
        from evals.report import render
        print(render(result, current,
                     run_url=os.environ.get("GITHUB_RUN_URL", "")))

    # Exit code IS the gate. Warnings and improvements do not block.
    sys.exit(1 if not result.passed else 0)
