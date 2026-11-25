"""Write what a screening call learned about a job back to its `run_jobs` row."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.eligibility.result import EligibilityResult
from src.config.constants import MAX_SCREEN_ATTEMPTS
from src.db.models import RunJob


async def save_verdict(
    session: AsyncSession,
    run_id: UUID,
    job_id: UUID,
    result: EligibilityResult,
    screening_hash: str,
    now: datetime,
) -> None:
    """Mark the job `done` with its verdict. A row that is not `processing` is left as it is,
    so a result can never overwrite one another call already finished."""
    await session.execute(
        update(RunJob)
        .where(RunJob.run_id == run_id, RunJob.job_id == job_id, RunJob.status == "processing")
        .values(
            status="done",
            claimed_at=None,
            last_error="",
            eligibility=result.verdict,
            eligibility_reason=result.reason,
            eligibility_quotes=result.quotes,
            recruiter_questions=result.recruiter_questions,
            profile_questions=result.profile_questions,
            flags=result.warnings,
            screening_hash=screening_hash,
            screened_at=now,
        )
    )


async def record_failure(session: AsyncSession, run_id: UUID, job_id: UUID, error: str) -> None:
    """Give the job another chance, or give up once it has used all its attempts.

    `attempts` was already counted when the job was claimed, so this decision needs no counter
    of its own: below the limit the job goes back to `pending` for the next call.
    """
    await session.execute(
        update(RunJob)
        .where(RunJob.run_id == run_id, RunJob.job_id == job_id, RunJob.status == "processing")
        .values(
            status=case((RunJob.attempts >= MAX_SCREEN_ATTEMPTS, "failed"), else_="pending"),
            claimed_at=None,
            last_error=error,
        )
    )
