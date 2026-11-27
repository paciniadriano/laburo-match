"""Extract the facts of one claimed job, never raising for that job's own failure.

Each call opens its own session and commits its result: a session is not safe to share between
concurrent tasks, and a result committed before a cancellation is not paid twice (the next
round finds it in the extraction cache).
"""

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


async def extract_one(
    sessions: async_sessionmaker[AsyncSession], job_id: UUID
) -> ExtractionOutcome:
    try:
        async with sessions() as session:
            job = await session.get_one(Job, job_id)
            extracted = await extract_job_facts(session, job)
            await session.commit()
        return ExtractionOutcome(job_id, extracted)
    except Exception as error:  # one bad job must not stop the others; the caller decides
        # The class only, in the log and in the outcome: a message can quote the posting text,
        # which is third-party content that may hold contact data.
        error_class = type(error).__name__
        logger.warning("extraction failed", extra={"job_id": str(job_id), "error": error_class})
        return ExtractionOutcome(job_id, None, error=error_class)
