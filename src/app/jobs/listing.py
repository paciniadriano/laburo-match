"""Read the jobs a user already has a verdict for, one page at a time.

Each job is shown with the user's most recent finished row across all their runs, so a job
seen in several searches appears once, with its latest judgement.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import PREFILTER_REASON_TEXT, SOURCE_LABELS
from src.db.models import Job, RunJob
from src.models.listing import ListedJob, ListStatus


async def list_judged_jobs(
    session: AsyncSession,
    user_id: UUID,
    status: ListStatus,
    limit: int,
    offset: int,
    current_hash: str,
    now: datetime,
) -> tuple[list[ListedJob], int]:
    """One page of jobs in `status` and the total; eligible first, then the newest posting."""
    latest = (
        select(RunJob)
        .where(RunJob.user_id == user_id, RunJob.status == "done")
        .order_by(RunJob.job_id, RunJob.screened_at.desc().nulls_last())
        .distinct(RunJob.job_id)
        .subquery()
    )
    row = latest.c
    left_out = or_(row.prefilter_reason != "", row.eligibility == "not_eligible")
    in_status = left_out if status == "filtered" else ~left_out

    total = await session.scalar(select(func.count()).select_from(latest).where(in_status)) or 0
    eligible_first = case((row.eligibility == "eligible", 0), else_=1)
    rows = await session.execute(
        select(
            Job,
            row.prefilter_reason,
            row.eligibility,
            row.eligibility_reason,
            row.screening_hash,
            row.screened_at,
        )  # fmt: skip
        .join(Job, Job.id == row.job_id)
        .where(in_status)
        .order_by(eligible_first, Job.posted_at.desc().nulls_last(), Job.title, Job.id)
        .limit(limit)
        .offset(offset)
    )
    items = [
        _listed(job, prefilter, verdict, reason, judged_hash, screened_at, now, current_hash)
        for job, prefilter, verdict, reason, judged_hash, screened_at in rows.all()
    ]
    return items, total


def _listed(
    job: Job,
    prefilter_reason: str,
    eligibility: str,
    eligibility_reason: str,
    judged_hash: str,
    screened_at: datetime | None,
    now: datetime,
    current_hash: str,
) -> ListedJob:
    prefiltered = bool(prefilter_reason)
    return ListedJob(
        job_id=str(job.id),
        title=job.title,
        company=job.company,
        source=SOURCE_LABELS.get(job.source, job.source),
        verdict="filtered" if prefiltered else eligibility,  # pyright: ignore[reportArgumentType]
        reason=PREFILTER_REASON_TEXT.get(prefilter_reason, prefilter_reason)
        if prefiltered
        else eligibility_reason,
        apply_url=job.apply_url or job.url,
        posted_at=job.posted_at,
        days_since_update=(now - screened_at).days if screened_at else 0,
        closed=job.closed_at is not None,
        # A prefilter discard was never screened, so it has no profile fingerprint to compare.
        stale=not prefiltered and judged_hash != current_hash,
    )
