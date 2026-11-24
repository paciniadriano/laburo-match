"""Deterministic filters that discard a job only when it cannot be useful."""

from datetime import datetime, timedelta

from src.app.jobs.candidate import Candidate


def prefilter_reason(candidate: Candidate, now: datetime, max_age_days: int) -> str | None:
    """Why the job is discarded, or None to keep it. A job with no date is kept: absence of
    information is never a reason to discard."""
    if candidate.closed_at is not None:
        return "closed"
    if candidate.posted_at is not None and now - candidate.posted_at > timedelta(days=max_age_days):
        return "too_old"
    return None
