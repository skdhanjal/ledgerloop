from ledgerloop.graph.reducers import append_capped, dedupe_keep_severest, merge_by_index


def test_merge_by_index_overwrites_retried_branch():
    # A retried write at the same index should replace, not duplicate.
    current = {0: {"line_index": 0, "matched": False}}
    update = {0: {"line_index": 0, "matched": True}}

    merged = merge_by_index(current, update)

    assert merged == {0: {"line_index": 0, "matched": True}}


def test_merge_by_index_keeps_other_indices():
    current = {0: {"line_index": 0, "matched": True}}
    update = {1: {"line_index": 1, "matched": True}}

    merged = merge_by_index(current, update)

    assert merged == {
        0: {"line_index": 0, "matched": True},
        1: {"line_index": 1, "matched": True},
    }


def test_dedupe_keep_severest_replaces_lower_severity():
    current = [{"code": "price_variance", "severity": 1, "message": "1% over"}]
    update = [{"code": "price_variance", "severity": 3, "message": "8% over"}]

    merged = dedupe_keep_severest(current, update)

    assert merged == [{"code": "price_variance", "severity": 3, "message": "8% over"}]


def test_dedupe_keep_severest_ignores_lower_severity_update():
    current = [{"code": "price_variance", "severity": 3, "message": "8% over"}]
    update = [{"code": "price_variance", "severity": 1, "message": "1% over"}]

    merged = dedupe_keep_severest(current, update)

    assert merged == [{"code": "price_variance", "severity": 3, "message": "8% over"}]


def test_dedupe_keep_severest_keeps_distinct_codes():
    current = [{"code": "price_variance", "severity": 1, "message": "x"}]
    update = [{"code": "missing_po", "severity": 2, "message": "y"}]

    merged = dedupe_keep_severest(current, update)

    assert {e["code"] for e in merged} == {"price_variance", "missing_po"}


def test_append_capped_trims_to_cap():
    reducer = append_capped(3)

    merged = reducer([1, 2, 3], [4])

    assert merged == [2, 3, 4]


def test_append_capped_under_cap_just_appends():
    reducer = append_capped(200)

    merged = reducer([1, 2], [3])

    assert merged == [1, 2, 3]
