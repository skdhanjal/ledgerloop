"""Tests for the evaluators themselves. An evaluator you have not tested
is a measurement you cannot trust."""
import pytest

from evals.calibrate import cohens_kappa
from evals.evaluators import (decision_correct, evidence_grounded,
                              exception_detection, extraction_exact)


# ---- deterministic evaluators -----------------------------------------
def test_extraction_scores_per_field():
    truth = {"vendor": "Kestrel", "invoice_no": "INV-1", "total": 100.0,
             "subtotal": 90.0, "tax": 10.0, "po_number": "PO-1"}
    assert extraction_exact(truth, truth)["score"] == 1.0
    partial = extraction_exact({**truth, "total": 999.0}, truth)
    assert partial["per_field"]["total"] is False
    assert partial["score"] < 1.0


def test_missed_and_spurious_are_reported_separately():
    """They fail differently: missed = wrong payment, spurious = analyst time."""
    out = exception_detection(["price_variance", "duplicate"],
                              ["price_variance", "short_shipment"])
    assert out["missed"] == ["short_shipment"]
    assert out["spurious"] == ["duplicate"]
    assert out["precision"] == 0.5 and out["recall"] == 0.5


def test_grounding_catches_an_invented_figure():
    verdict = {"root_cause": "billed 114.75 vs PO 85.00"}
    traj = [{"tool": "lookup_po", "result": "unit_price=85.00"}]
    out = evidence_grounded(verdict, traj)
    assert out["score"] == 0.0
    assert "114.75" in out["unsupported_figures"]


def test_grounding_passes_when_every_figure_is_observed():
    verdict = {"root_cause": "billed 114.75 vs PO 85.00"}
    traj = [{"tool": "lookup_po", "result": "unit_price=85.00"},
            {"tool": "read_invoice", "result": "unit_price=114.75"}]
    assert evidence_grounded(verdict, traj)["score"] == 1.0


# ---- calibration maths ------------------------------------------------
def test_kappa_is_one_for_perfect_agreement():
    assert cohens_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == pytest.approx(1.0)


def test_kappa_is_zero_when_the_judge_always_says_the_same_thing():
    """THE point of kappa: raw agreement here is 80%, which flatters a judge
    that is doing no work at all."""
    human = [4, 4, 4, 4, 2]
    judge = [4, 4, 4, 4, 4]
    assert sum(h == j for h, j in zip(human, judge)) / 5 == 0.8
    assert cohens_kappa(human, judge) == pytest.approx(0.0, abs=0.01)


def test_kappa_penalises_systematic_bias():
    human = [3, 3, 4, 4, 5]
    generous = [4, 4, 5, 5, 5]           # judge is one point kinder
    assert cohens_kappa(human, generous) < 0.5
