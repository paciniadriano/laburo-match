"""Read the jobs a user already has a verdict for, one page at a time.

Each job is shown with the user's most recent finished row across all their runs, so a job
seen in several searches appears once, with its latest judgement.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import PREFILTER_REASON_TEXT, SOURCE_LABELS
from src.core.relevance import title_relevance
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
    target_roles: tuple[str, ...] = (),
) -> tuple[list[ListedJob], int]:
    """One page of jobs in `status` and the total.

    `all`: eligible first, then the title closest to `target_roles`, then the newest posting.
    `filtered`: the newest first.
    """
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
    )
    # Ordered in Python: title relevance is not something SQL can compute. A user has at most a
    # few hundred judged jobs, so reading them all to sort one page is cheap.
    ordered = sorted(rows.all(), key=lambda r: _order(r[0], r[2], status, target_roles))
    page = ordered[offset : offset + limit]
    items = [
        _listed(job, prefilter, verdict, reason, judged_hash, screened_at, now, current_hash)
        for job, prefilter, verdict, reason, judged_hash, screened_at in page
    ]
    return items, len(ordered)


def _order(
    job: Job, eligibility: str | None, status: ListStatus, target_roles: tuple[str, ...]
) -> tuple[int, int, float, str, str]:
    newest = -(job.posted_at.timestamp() if job.posted_at else 0.0)
    if status == "filtered":
        return (0, 0, newest, job.title, str(job.id))
    relevance = -title_relevance(job.title, target_roles)
    return (0 if eligibility == "eligible" else 1, relevance, newest, job.title, str(job.id))


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
