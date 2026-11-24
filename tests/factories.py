"""Small builders so each test states only what it cares about."""

from typing import Any

from src.models.job_facts import JobFacts, Restriction


def make_restriction(**changes: Any) -> Restriction:
    base: dict[str, Any] = {
        "kind": "location",
        "evidence_kind": "explicit",
        "quotes": ["Remote within Latin America"],
        "places": ["Latin America"],
        "place_scope": "region",
    }
    return Restriction(**{**base, **changes})


def make_facts(**changes: Any) -> JobFacts:
    base: dict[str, Any] = {
        "is_job_posting": True,
        "language": "en",
        "work_modality": "remote",
        "restrictions": [],
        "office_locations": [],
        "apply_email": "",
    }
    return JobFacts(**{**base, **changes})
