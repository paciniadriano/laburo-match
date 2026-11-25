"""Extract the facts of several jobs at once without blowing up cost, the pool or the host timeout.

Three rules shape this module:
- The first job runs alone: the provider caches the shared prompt prefix only after it has
  answered once, so jobs launched together would all pay full price for it.
- The rest run in parallel behind a semaphore, so the provider's rate limit and our connection
  pool are never hit by the whole batch at once.
- Every task opens its own session and commits its own result. A session is not safe to share
  between concurrent tasks, and a result committed before a cancellation is not paid twice.
"""

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.jobs.extraction import Extracted, extract_job_facts
from src.db.models import Job

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractionOutcome:
    job_id: UUID
    extracted: Extracted | None  # None when the extraction failed
    error: str = ""  # the error class only: messages may quote posting text


async def _extract_one(
    sessions: async_sessionmaker[AsyncSession], job_id: UUID
) -> ExtractionOutcome:
    try:
        async with sessions() as session:
            job = await session.get_one(Job, job_id)
            extracted = await extract_job_facts(session, job)
            await session.commit()
        return ExtractionOutcome(job_id, extracted)
    except Exception as error:  # one bad job must not stop the others; the caller decides
        logger.warning("extraction failed", extra={"job_id": str(job_id), "error": repr(error)})
        return ExtractionOutcome(job_id, None, error=type(error).__name__)


async def extract_jobs(
    sessions: async_sessionmaker[AsyncSession], job_ids: list[UUID], concurrency: int
) -> list[ExtractionOutcome]:
    """One outcome per job, in the order given. Never raises for a single job's failure."""
    if not job_ids:
        return []
    first = await _extract_one(sessions, job_ids[0])

    gate = asyncio.Semaphore(concurrency)

    async def limited(job_id: UUID) -> ExtractionOutcome:
        async with gate:
            return await _extract_one(sessions, job_id)

    rest = await asyncio.gather(*(limited(job_id) for job_id in job_ids[1:]))
    return [first, *rest]
