"""Search runs: what a user has already seen, and creating a run with its queue of jobs."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.search.plan import SearchPlan
from src.app.search.selection import Selection
from src.config.constants import RUN_TTL_HOURS
from src.db.models import RunJob, SearchRun


async def job_ids_already_seen(
    session: AsyncSession, user_id: UUID, job_ids: list[UUID]
) -> set[UUID]:
    """Jobs this user already has a row for. Jobs left over a previous cap have none."""
    rows = await session.scalars(
        select(RunJob.job_id).where(RunJob.user_id == user_id, RunJob.job_id.in_(job_ids))
    )
    return set(rows)


async def create_run(
    session: AsyncSession,
    user_id: UUID,
    plan: SearchPlan,
    selection: Selection,
    funnel: dict[str, Any],
    now: datetime,
) -> SearchRun:
    """Save the run with a `pending` row per job to screen and a `done` row per discard."""
    run = SearchRun(
        id=uuid4(),
        user_id=user_id,
        kind="search",
        plan=plan.to_json(),
        expires_at=now + timedelta(hours=RUN_TTL_HOURS),
        funnel=funnel,
    )
    session.add(run)
    await session.flush()  # the run must exist before the rows that point to it

    position = 0
    for candidate in selection.to_screen:
        position += 1
        session.add(
            RunJob(run_id=run.id, job_id=candidate.job_id, user_id=user_id, position=position)
        )
    for candidate, reason in selection.discarded:
        position += 1
        session.add(
            RunJob(
                run_id=run.id,
                job_id=candidate.job_id,
                user_id=user_id,
                position=position,
                status="done",
                prefilter_reason=reason,
                screened_at=now,
            )
        )
    await session.flush()
    return run
