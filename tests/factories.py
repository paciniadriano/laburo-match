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


def make_source_job(external_id: str, title: str = "Frontend Engineer", **changes: Any) -> Any:
    """A normalized job as a source adapter would return it. Each one is a different opening
    (its own employer) unless a test says otherwise."""
    from datetime import UTC, datetime

    from src.sources.base import SourceJob

    base: dict[str, Any] = {
        "source": "getonbrd",
        "external_id": external_id,
        "title": title,
        "company": f"Company {external_id}",
        "url": f"https://www.getonbrd.com/jobs/{external_id}",
        "apply_url": f"https://www.getonbrd.com/jobs/{external_id}",
        "location_text": "Remote",
        "body": f"[description]\nWork on {title}",
        "language": "en",
        "posted_at": datetime(2026, 11, 23, 12, 0, tzinfo=UTC),
    }
    return SourceJob(**{**base, **changes})


async def queue_run(sessions: Any, jobs: int, job_changes: Any = None) -> tuple[Any, Any]:
    """A committed run for the seeded sample user with `jobs` pending jobs.

    Returns (user_id, run_id). Job `n` has external id `job-n` and title `Role n`;
    `job_changes(n)` may return extra `make_source_job` arguments for it. For tests that use
    the `committed_sessions` fixture, which needs data that other connections can see.
    """
    import json
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from src.app.jobs.store import upsert_shared_jobs
    from src.app.profile.seed import seed_sample_profile
    from src.db.models import RunJob, SearchRun
    from tests.conftest import SAMPLE_EVIDENCE

    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    async with sessions() as session:
        sample = json.loads(SAMPLE_EVIDENCE.read_text())
        user_id = (await seed_sample_profile(session, sample, max_job_age_days=30)).user_id
        source_jobs = [
            make_source_job(
                f"job-{n}", title=f"Role {n}", **(job_changes(n) if job_changes else {})
            )
            for n in range(jobs)
        ]
        candidates = await upsert_shared_jobs(session, source_jobs, now)
        run = SearchRun(
            id=uuid4(), user_id=user_id, kind="search", expires_at=now + timedelta(hours=24)
        )
        session.add(run)
        await session.flush()
        for position, candidate in enumerate(candidates, start=1):
            session.add(
                RunJob(run_id=run.id, job_id=candidate.job_id, user_id=user_id, position=position)
            )
        await session.commit()
        return user_id, run.id
