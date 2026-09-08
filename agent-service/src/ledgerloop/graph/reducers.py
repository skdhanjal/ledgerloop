"""Custom state reducers for InvoiceState.

Every reducer here has the signature LangGraph requires for an
`Annotated[T, reducer]` field: `(current, update) -> merged`. LangGraph
calls it once per node write that touches the field, passing the value
already in state and the value the node just returned -- never two node
outputs directly against each other. Reducer choice *is* the concurrency
policy: it decides what happens when two branches (a retried fan-out
branch, or two parallel branches, per Day 14's runtime-width matching)
write to the same field in the same superstep.
"""

from __future__ import annotations

from collections.abc import Callable


def merge_by_index[T](current: dict[int, T], update: dict[int, T]) -> dict[int, T]:
    """Merge a line-index-keyed dict, letting `update` overwrite `current`.

    Day 14 fans out one matcher branch per invoice line, keyed by line
    index. If a branch is retried (a transient failure, a resumed run),
    LangGraph replays it and it writes the same index again. Overwrite-
    by-key makes that idempotent: the second write replaces the first
    rather than the field silently duplicating an entry.
    """
    merged = dict(current)
    merged.update(update)
    return merged


def dedupe_keep_severest(current: list[dict], update: list[dict]) -> list[dict]:
    """Merge exception lists, keeping at most one entry per `code`.

    When both `current` and `update` carry an exception with the same
    `code`, the one with the higher `severity` wins. This is what lets
    the policy gate's rule cascade (Day 5) run multiple checks against
    the same invoice without the audit trail accumulating duplicate
    entries for the same exception every time a branch re-evaluates.
    """
    by_code: dict[str, dict] = {e["code"]: e for e in current}
    for exc in update:
        existing = by_code.get(exc["code"])
        if existing is None or exc["severity"] > existing["severity"]:
            by_code[exc["code"]] = exc
    return list(by_code.values())


def append_capped[T](cap: int) -> Callable[[list[T], list[T]], list[T]]:
    """Build a reducer that appends, then trims to the most recent `cap` entries.

    The cap lives *inside* the reducer, not in a node that has to
    remember to trim -- every write path, including nodes nobody has
    written yet, gets the bound for free.
    """

    def reducer(current: list[T], update: list[T]) -> list[T]:
        return [*current, *update][-cap:]

    return reducer
