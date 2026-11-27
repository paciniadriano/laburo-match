"""Deterministic filters that discard a job only when it cannot be useful."""

from datetime import datetime, timedelta

from src.app.jobs.candidate import Candidate
from src.core.places import mentions_area, resolve_places


def office_abroad(candidate: Candidate, country: str | None) -> bool:
    """Hybrid or on-site, with every office in a known country that is not the user's.

    A border cannot be crossed every day, so the city does not matter. Modality and country
    come from the source's own fields, not from reading the text. Any doubt keeps the job for
    screening: an unknown user country, a place the table cannot read, a list that includes the
    user's country, or prose that names a place that may include it ("offices across LATAM").
    """
    if country is None or candidate.modality not in ("hybrid", "onsite"):
        return False
    declared = [place.strip() for place in candidate.location_text.split(",") if place.strip()]
    places = resolve_places(declared)
    if not places.countries or places.unknown or places.ambiguous or places.worldwide:
        return False
    if country in places.countries:
        return False
    return not mentions_area(f"{candidate.title}\n{candidate.raw_text}", country)


def prefilter_reason(
    candidate: Candidate, now: datetime, max_age_days: int, country: str | None = None
) -> str | None:
    """Why the job is discarded, or None to keep it. A job with no date is kept: absence of
    information is never a reason to discard."""
    if candidate.closed_at is not None:
        return "closed"
    if candidate.posted_at is not None and now - candidate.posted_at > timedelta(days=max_age_days):
        return "too_old"
    if office_abroad(candidate, country):
        return "office_abroad"
    return None
