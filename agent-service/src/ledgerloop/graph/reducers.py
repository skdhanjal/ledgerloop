"""Custom reducers for InvoiceState fields.

A reducer has the signature `(current, update) -> merged`. LangGraph calls
it once per node write that touches the field, never comparing two nodes'
outputs directly against each other. Reducer choice is the concurrency
policy for that field.
"""

from __future__ import annotations

from collections.abc import Callable


def merge_by_index[T](current: dict[int, T], update: dict[int, T]) -> dict[int, T]:
    """Overwrite by key, so a retried write at the same index replaces
    rather than duplicates."""
    merged = dict(current)
    merged.update(update)
    return merged


def dedupe_keep_severest(current: list[dict], update: list[dict]) -> list[dict]:
    """Keep at most one entry per `code`, preferring the higher `severity`."""
    by_code: dict[str, dict] = {e["code"]: e for e in current}
    for exc in update:
        existing = by_code.get(exc["code"])
        if existing is None or exc["severity"] > existing["severity"]:
            by_code[exc["code"]] = exc
    return list(by_code.values())


def append_capped[T](cap: int) -> Callable[[list[T], list[T]], list[T]]:
    """Build a reducer that appends, then trims to the most recent `cap` entries."""

    def reducer(current: list[T], update: list[T]) -> list[T]:
        return [*current, *update][-cap:]

    return reducer
