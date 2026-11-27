"""Pure helpers for evidence items: years and content hash."""

import hashlib
import json
from collections.abc import Sequence
from datetime import date


def union_years(periods: Sequence[Sequence[str]]) -> float:
    """Years covered by ISO-date intervals, counting overlapping time once.

    A skill used in two jobs that overlap for a year is not worth two extra years of experience.
    """
    intervals = sorted(
        (date.fromisoformat(start), date.fromisoformat(end)) for start, end in periods
    )
    merged: list[list[date]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    days = sum((end - start).days for start, end in merged)
    return round(days / 365.25, 2)


def content_hash(
    *, kind: str, name: str, strength: str, periods: Sequence[Sequence[str]], quote: str
) -> str:
    """Fingerprint of everything that can change a match result.

    Cached links record the hash of the evidence they used; a different hash means the link
    must be recomputed.
    """
    payload = {"kind": kind, "name": name, "strength": strength, "periods": periods, "quote": quote}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
