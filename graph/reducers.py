"""Reducers: the merge rules for our state channels.

Every function here is pure, cheap, and tolerant of a None current value -
these run inside the commit path and may be called more than once per step.
"""
from typing import Any

SEVERITY = {"low": 0, "medium": 1, "high": 2}
MAX_EXCEPTIONS = 40
MAX_AUDIT = 200


def dedupe_exceptions(current: list[dict] | None, update: list[dict] | None) -> list[dict]:
    """One entry per exception code, keeping the most severe occurrence.

    Insertion order is preserved so the audit trail reads chronologically.
    """
    merged: dict[str, dict] = {e["code"]: e for e in (current or [])}
    for e in (update or []):
        seen = merged.get(e["code"])
        if seen is None or SEVERITY[e["severity"]] > SEVERITY[seen["severity"]]:
            merged[e["code"]] = e
    out = list(merged.values())
    return out[-MAX_EXCEPTIONS:]


def merge_line_matches(current: list[dict] | None, update: list[dict] | None) -> list[dict]:
    """Accumulate per-line match results, keyed by line index.

    Day 14 fans out one node per invoice line, so several of these land in the
    same super-step. Re-running a line (a retry, or a resumed thread) must
    replace that line's result rather than append a second copy - which is what
    plain operator.add would do.
    """
    merged: dict[int, dict] = {m["line_index"]: m for m in (current or [])}
    for m in (update or []):
        merged[m["line_index"]] = m
    return [merged[k] for k in sorted(merged)]


def bounded_audit(current: list[Any] | None, update: list[Any] | None) -> list[Any]:
    """Append-only audit trail with a hard cap on length.

    The cap lives here, not in a node: state is serialized into every
    checkpoint, so an unbounded channel is a slow memory leak on disk.
    """
    return ((current or []) + (update or []))[-MAX_AUDIT:]
