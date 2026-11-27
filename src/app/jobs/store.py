"""Save jobs coming from a source."""

import hashlib
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.jobs.candidate import Candidate
from src.core.text import normalize_name
from src.db.models import Job
from src.sources.base import SourceJob

# Columns refreshed when a known job is seen again. `id`, `first_seen_at` and the dedupe
# columns stay as they were: a job keeps its identity when its text changes.
_REFRESHED = (
    "url", "apply_url", "company", "company_normalized", "title", "location_text", "modality",
    "raw_text",
    "content_hash", "language", "posted_at", "last_seen_at",
)  # fmt: skip


# What the search steps need of each stored job, in `Candidate` field order.
_CANDIDATE_COLUMNS = (
    Job.id, Job.title, Job.posted_at, Job.closed_at, Job.modality, Job.location_text, Job.raw_text,
    Job.company_normalized,
)  # fmt: skip


def job_content_hash(title: str, body: str) -> str:
    """Changes whenever the posting text changes; extraction results are cached against it."""
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()


async def upsert_shared_jobs(
    session: AsyncSession, jobs: list[SourceJob], now: datetime
) -> list[Candidate]:
    """Insert new jobs and refresh known ones, in one statement; returns what is now stored."""
    # Two rows with the same key in one statement make Postgres refuse it, so keep the last.
    unique = {(job.source, job.external_id): job for job in jobs}
    if not unique:
        return []
    rows = [
        {
            "source": job.source,
            "external_id": job.external_id,
            "owner_user_id": None,  # NULL = shared, from a source
            "url": job.url,
            "apply_url": job.apply_url,
            "company": job.company,
            "company_normalized": normalize_name(job.company),
            "title": job.title,
            "location_text": job.location_text,
            "modality": job.modality,
            "raw_text": job.body,
            "content_hash": job_content_hash(job.title, job.body),
            "language": job.language,
            "posted_at": job.posted_at,
            "first_seen_at": now,
            "last_seen_at": now,
        }
        for job in unique.values()
    ]
    statement = insert(Job)
    statement = statement.on_conflict_do_update(
        index_elements=["source", "external_id"],
        index_where=text("owner_user_id IS NULL"),  # the partial index of shared jobs
        set_={**{column: statement.excluded[column] for column in _REFRESHED}, "closed_at": None},
    ).returning(*_CANDIDATE_COLUMNS)
    result = await session.execute(statement, rows)
    return [Candidate(*row) for row in result.all()]
