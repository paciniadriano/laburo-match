"""Deterministic filters that discard a job only when it cannot be useful."""

from datetime import datetime, timedelta

from src.app.jobs.candidate import Candidate
from src.core.places import resolve_places


def _declared_elsewhere(declared: str, country: str) -> bool:
    """Every place the source declares is a known country that is not the user's.

    The employer's own policy decides, whatever the prose says (user decision: a "Mexico only"
    policy rules out a user in Argentina even if a company blurb says "work globally"). Doubt
    about the declaration itself keeps the job: a place the table cannot read, a list that
    includes the user's country, or "anywhere".
    """
    places = resolve_places([place.strip() for place in declared.split(",") if place.strip()])
    if not places.countries or places.unknown or places.ambiguous or places.worldwide:
        return False
    return country not in places.countries


def office_abroad(candidate: Candidate, country: str | None) -> bool:
    """Hybrid or on-site, with every office in a known country that is not the user's.

    A border cannot be crossed every day, so the city does not matter. Modality and country
    come from the source's own fields, not from reading the text.
    """
    if country is None or candidate.modality not in ("hybrid", "onsite"):
        return False
    return _declared_elsewhere(candidate.location_text, country)


def residence_abroad(candidate: Candidate, country: str | None) -> bool:
    """Remote, but the source says candidates must live in countries that are not the user's
    (Get on Board's "Locally remote only: candidates must reside in Chile")."""
    if country is None or candidate.modality != "remote":
        return False
    return _declared_elsewhere(candidate.residence_text, country)


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
    if residence_abroad(candidate, country):
        return "residence_abroad"
    return None
