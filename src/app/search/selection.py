"""Decide which new jobs are worth screening now: filter, rank, cap."""

from dataclasses import dataclass
from datetime import datetime

from src.app.jobs.candidate import Candidate
from src.app.search.prefilter import prefilter_reason
from src.app.search.relevance import rank


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


def select_for_screening(
    fresh: list[Candidate],
    target_roles: tuple[str, ...],
    now: datetime,
    max_age_days: int,
    limit: int,
) -> Selection:
    kept: list[Candidate] = []
    discarded: list[tuple[Candidate, str]] = []
    for candidate in fresh:
        reason = prefilter_reason(candidate, now, max_age_days)
        if reason:
            discarded.append((candidate, reason))
        else:
            kept.append(candidate)
    ranked = rank(kept, target_roles)
    return Selection(ranked[:limit], discarded, ranked[limit:])
