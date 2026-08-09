"""Tests for the gate itself. A gate you have not tested will not hold."""
import pytest

from evals.gate import BAND_PP, NOISE_FLOOR_PP, check

BASE = {
    "decision_accuracy": 0.87, "extraction_match": 0.94, "exception_recall": 0.89,
    "judge_mean": 4.1,
    "by_stratum": {"clean": 1.0, "price_variance": 0.95, "uom_mismatch": 0.86,
                   "multi_exception": 0.60},
}


def current(**over):
    base = {**BASE, "judge_kappa": 0.81, "baseline_date": "2026-07-31"}
    return {**base, **over}


# ---- noise tolerance --------------------------------------------------
def test_small_drop_inside_the_noise_floor_passes():
    """The whole point: do not fail on run-to-run variation."""
    r = check(current(decision_accuracy=0.87 - NOISE_FLOOR_PP / 200), BASE)
    assert r.passed


def test_drop_beyond_the_band_fails():
    r = check(current(decision_accuracy=0.87 - (BAND_PP + 1) / 100), BASE)
    assert not r.passed
    assert "decision_accuracy" in r.failures[0]


def test_drop_between_floor_and_band_warns_without_failing():
    r = check(current(decision_accuracy=0.87 - (NOISE_FLOOR_PP + 0.5) / 100), BASE)
    assert r.passed
    assert r.warnings


# ---- hard gates -------------------------------------------------------
def test_a_single_double_payment_fails_regardless_of_scores():
    r = check(current(double_pay_incidents=1), BASE)
    assert not r.passed
    assert "double_pay" in r.failures[0]


def test_pii_leak_fails_even_with_perfect_accuracy():
    r = check(current(decision_accuracy=1.0, pii_events_leaked=1), BASE)
    assert not r.passed


# ---- stratum protection ----------------------------------------------
def test_a_collapsed_stratum_fails_even_when_the_aggregate_holds():
    """THE case for per-stratum gating: uom_mismatch goes 86% -> 20% while
    decision_accuracy barely moves, because it is 14 cases out of 100."""
    broken = {**BASE["by_stratum"], "uom_mismatch": 0.20}
    r = check(current(decision_accuracy=0.86, by_stratum=broken), BASE)
    assert not r.passed
    assert any("uom_mismatch" in f for f in r.failures)


def test_missing_stratum_fails_loudly():
    partial = {k: v for k, v in BASE["by_stratum"].items() if k != "clean"}
    r = check(current(by_stratum=partial), BASE)
    assert not r.passed


# ---- judge eligibility ------------------------------------------------
def test_judge_scores_do_not_gate_below_kappa_06():
    """An uncalibrated judge must never block a merge (Day 22)."""
    r = check(current(judge_kappa=0.45, judge_mean=3.0), BASE)
    assert r.passed
    assert any("kappa" in w for w in r.warnings)


def test_judge_scores_gate_when_calibration_is_strong():
    r = check(current(judge_kappa=0.85, judge_mean=3.2), BASE)
    assert not r.passed


# ---- improvements -----------------------------------------------------
def test_large_unexplained_improvement_is_flagged():
    """A big jump usually means a broken evaluator, not genius."""
    r = check(current(decision_accuracy=0.99), BASE)
    assert r.passed
    assert r.improvements
