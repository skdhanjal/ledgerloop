"""Reducer unit tests. Pure functions, no graph, no model, no network."""
import pytest

from graph.reducers import (MAX_AUDIT, bounded_audit, dedupe_exceptions,
                            merge_line_matches)


def exc(code, severity="low"):
    return {"code": code, "severity": severity, "detail": f"{code}/{severity}"}


# ---- dedupe_exceptions -------------------------------------------------
def test_handles_none_current():
    """A reducer's first call has no current value. Written as `a + b` this crashes."""
    assert dedupe_exceptions(None, [exc("price_variance")]) == [exc("price_variance")]


def test_dedupes_by_code():
    out = dedupe_exceptions([exc("missing_po")], [exc("missing_po")])
    assert len(out) == 1


def test_keeps_most_severe():
    out = dedupe_exceptions([exc("price_variance", "low")],
                            [exc("price_variance", "high")])
    assert out[0]["severity"] == "high"


def test_lower_severity_does_not_downgrade():
    out = dedupe_exceptions([exc("price_variance", "high")],
                            [exc("price_variance", "low")])
    assert out[0]["severity"] == "high"


def test_is_pure_does_not_mutate_arguments():
    current = [exc("a")]
    snapshot = [dict(e) for e in current]
    dedupe_exceptions(current, [exc("b")])
    assert current == snapshot


# ---- merge_line_matches ------------------------------------------------
def test_parallel_writes_all_survive():
    """Simulates three matchers committing in one super-step."""
    state = None
    for i in range(3):
        state = merge_line_matches(state, [{"line_index": i, "ok": True}])
    assert [m["line_index"] for m in state] == [0, 1, 2]


def test_rerun_replaces_rather_than_appends():
    """A retried or resumed line must not produce a duplicate row."""
    state = merge_line_matches(None, [{"line_index": 1, "ok": False}])
    state = merge_line_matches(state, [{"line_index": 1, "ok": True}])
    assert len(state) == 1 and state[0]["ok"] is True


def test_output_is_sorted_by_line_index():
    state = merge_line_matches(None, [{"line_index": 5}, {"line_index": 2}])
    assert [m["line_index"] for m in state] == [2, 5]


# ---- bounded_audit -----------------------------------------------------
def test_audit_appends():
    assert bounded_audit(["a"], ["b"]) == ["a", "b"]


def test_audit_caps_and_keeps_newest():
    out = bounded_audit(list(range(MAX_AUDIT)), ["newest"])
    assert len(out) == MAX_AUDIT and out[-1] == "newest"


@pytest.mark.parametrize("current,update", [(None, None), (None, []), ([], None)])
def test_empty_inputs_never_crash(current, update):
    assert bounded_audit(current, update) == []
