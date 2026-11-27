"""Turn the state of a run into what `screen_batch` returns: the best jobs judged so far."""

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.eligibility.result import DISCLAIMER
from src.config.constants import SHORTLIST_SIZE, SOURCE_LABELS
from src.core.relevance import title_relevance
from src.db.models import Job, RunJob
from src.models.screening import JobCard, ScreenBatchResult


def _hint_partial(remaining: int) -> str:
    return (
        f"Show these results to the user now. {remaining} jobs are not checked yet: offer to "
        "check more, and call screen_batch again with the same run_id only if the user wants "
        "it. Use the job_id of each card."
    )


_HINT_DONE = (
    "Every job of this search is checked: there are no more to check. Present the shortlist "
    "with its quotes and the disclaimer, ask the profile questions once, and tell the user how "
    "many jobs could not be processed, if any. Use the job_id of each card. If the user asks "
    "for more: list_jobs shows every judged job; new postings need a new search later."
)


async def _counts(session: AsyncSession, query: Select[Any, int], group_by: Any) -> dict[Any, int]:
    """Rows of (value, count) as a dict. `dict(result)` would not work: a result has `keys()`."""
    rows = await session.execute(query.group_by(group_by))
    return {value: count for value, count in rows.all()}


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


async def build_screen_result(
    session: AsyncSession, run_id: UUID, target_roles: tuple[str, ...] = ()
) -> ScreenBatchResult:
    """`target_roles` are the roles the search looked for: closer titles go first."""
    # Rows a prefilter already discarded are `done` too, but nobody screened them.
    screening_rows = RunJob.prefilter_reason == ""
    by_status = await _counts(
        session,
        select(RunJob.status, func.count()).where(RunJob.run_id == run_id, screening_rows),
        RunJob.status,
    )
    processed = by_status.get("done", 0)
    failed = by_status.get("failed", 0)
    remaining = by_status.get("pending", 0) + by_status.get("processing", 0)

    totals = await _counts(
        session,
        select(RunJob.eligibility, func.count()).where(
            RunJob.run_id == run_id, RunJob.status == "done", screening_rows
        ),
        RunJob.eligibility,
    )
    return ScreenBatchResult(
        status="partial" if remaining else "done",
        processed=processed,
        failed=failed,
        remaining=remaining,
        next_step_hint=_hint_partial(remaining) if remaining else _HINT_DONE,
        shortlist=await _shortlist(session, run_id, target_roles),
        eligible_total=totals.get("eligible", 0),
        doubtful_total=totals.get("doubtful", 0),
        discarded=await _discarded(session, run_id, totals.get("not_eligible", 0)),
        profile_questions=await _profile_questions(session, run_id),
        disclaimer=DISCLAIMER,
    )


async def _shortlist(
    session: AsyncSession, run_id: UUID, target_roles: tuple[str, ...]
) -> list[JobCard]:
    """Eligible before doubtful, then the title closest to the roles searched (a stand-in for
    the fit band until matching exists, phase 5), then the newest posting."""
    rows = await session.execute(
        select(RunJob, Job)
        .join(Job, Job.id == RunJob.job_id)
        .where(
            RunJob.run_id == run_id,
            RunJob.status == "done",
            RunJob.eligibility.in_(("eligible", "doubtful")),
        )
    )

    def most_useful_first(pair: tuple[RunJob, Job]) -> tuple[int, int, float, int]:
        run_job, job = pair
        return (
            0 if run_job.eligibility == "eligible" else 1,
            -title_relevance(job.title, target_roles),
            -(job.posted_at.timestamp() if job.posted_at else 0.0),
            run_job.position,
        )

    best = sorted(((run_job, job) for run_job, job in rows.all()), key=most_useful_first)
    return [
        JobCard(
            job_id=str(job.id),
            title=job.title,
            company=job.company,
            source=SOURCE_LABELS.get(job.source, job.source),
            eligibility="eligible" if run_job.eligibility == "eligible" else "doubtful",
            reason=run_job.eligibility_reason,
            quotes=run_job.eligibility_quotes,
            recruiter_questions=run_job.recruiter_questions,
            warnings=run_job.flags,
            apply_url=job.apply_url or job.url,
            posted_at=job.posted_at,
        )
        for run_job, job in best[:SHORTLIST_SIZE]
    ]


async def _discarded(session: AsyncSession, run_id: UUID, not_eligible: int) -> dict[str, int]:
    """Prefilter discards by reason, plus the jobs screening found not eligible."""
    counts = await _counts(
        session,
        select(RunJob.prefilter_reason, func.count()).where(
            RunJob.run_id == run_id, RunJob.prefilter_reason != ""
        ),
        RunJob.prefilter_reason,
    )
    if not_eligible:
        counts["not_eligible"] = not_eligible
    return counts


async def _profile_questions(session: AsyncSession, run_id: UUID) -> list[str]:
    rows = await session.scalars(
        select(RunJob.profile_questions)
        .where(RunJob.run_id == run_id, RunJob.status == "done")
        .order_by(RunJob.position)
    )
    return _unique([question for questions in rows for question in questions])
