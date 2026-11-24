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


def gob_item(external_id: str = "job-1", **attributes: Any) -> dict[str, Any]:
    """One item of a Get on Board jobs response, in the shape the real API returns."""
    base: dict[str, Any] = {
        "title": "Frontend Engineer",
        "description_headline": "Requirements",
        "description": "<div>React experience</div><ul><li>TypeScript</li></ul>",
        "projects": "<div>We build payments.</div>",
        "functions": "<ul><li>Build UIs</li></ul>",
        "desirable": "<div>GraphQL</div>",
        "benefits": "<ul><li>Remote work</li></ul>",
        "remote_modality": "fully_remote",
        "countries": ["Chile"],
        "lang": "es",
        "published_at": 1795535105,
        "company": {"data": {"id": "acme", "type": "company", "attributes": {"name": "Acme"}}},
    }
    return {
        "id": external_id,
        "type": "job",
        "attributes": {**base, **attributes},
        "links": {"public_url": f"https://www.getonbrd.com/jobs/{external_id}"},
    }


def gob_page(items: list[Any], page: int = 1, total_pages: int = 1) -> dict[str, Any]:
    return {"data": items, "meta": {"page": page, "per_page": 120, "total_pages": total_pages}}
