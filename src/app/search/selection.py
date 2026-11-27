"""Decide which new jobs are worth screening now: filter, rank, cap."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.app.jobs.candidate import Candidate
from src.app.search.prefilter import prefilter_reason
from src.app.search.relevance import rank
from src.core.text import fold


@dataclass(frozen=True)
class Selection:
    to_screen: list[Candidate]  # the best ones, in display order
    discarded: list[tuple[Candidate, str]]  # with the reason, so every discard can be audited
    left_for_later: list[Candidate]  # fit nowhere under the cap; a later search will pick them up

    @property
    def discard_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _, reason in self.discarded:
            counts[reason] = counts.get(reason, 0) + 1
        return counts


_UNDATED = datetime.min.replace(tzinfo=UTC)  # a posting without a date sorts as the oldest


def _same_opening(candidate: Candidate) -> tuple[str, str, str] | None:
    """Same employer, same title, same place: the same opening posted twice. Without the
    employer's name two postings cannot be told apart, so they are never merged."""
    if not candidate.company:
        return None
    return (candidate.company, fold(candidate.title), fold(candidate.location_text))


def split_duplicates(
    candidates: list[Candidate],
) -> tuple[list[Candidate], list[tuple[Candidate, str]]]:
    """Keep the newest posting of each opening; the others are discarded as `duplicate`."""
    kept_ids: set[UUID] = set()
    seen: set[tuple[str, str, str]] = set()
    for candidate in sorted(candidates, key=lambda c: c.posted_at or _UNDATED, reverse=True):
        key = _same_opening(candidate)
        if key in seen:
            continue
        if key is not None:
            seen.add(key)
        kept_ids.add(candidate.job_id)
    kept = [c for c in candidates if c.job_id in kept_ids]  # in the order the search found them
    return kept, [(c, "duplicate") for c in candidates if c.job_id not in kept_ids]


def select_for_screening(
    fresh: list[Candidate],
    target_roles: tuple[str, ...],
    now: datetime,
    max_age_days: int,
    limit: int,
    country: str | None = None,
) -> Selection:
    """Filter first, cap after: a discarded job never takes a place under the cap."""
    kept: list[Candidate] = []
    discarded: list[tuple[Candidate, str]] = []
    for candidate in fresh:
        reason = prefilter_reason(candidate, now, max_age_days, country)
        if reason:
            discarded.append((candidate, reason))
        else:
            kept.append(candidate)
    kept, duplicates = split_duplicates(kept)
    discarded.extend(duplicates)
    ranked = rank(kept, target_roles)
    return Selection(ranked[:limit], discarded, ranked[limit:])
