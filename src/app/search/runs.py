"""Search runs: what a user has already seen, and creating a run with its queue of jobs."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.search.plan import SearchPlan
from src.app.search.selection import Selection
from src.config.constants import RUN_TTL_HOURS
from src.core.errors import RunExpiredError, RunNotFoundError
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


async def load_run(session: AsyncSession, user_id: UUID, run_id: str, now: datetime) -> SearchRun:
    """The user's run, or the error that says why it cannot be used.

    A run of another user is reported as not found: its existence is not the caller's business.
    """
    try:
        run = await session.scalar(
            select(SearchRun).where(SearchRun.id == UUID(run_id), SearchRun.user_id == user_id)
        )
    except ValueError:  # not a UUID
        run = None
    if run is None:
        raise RunNotFoundError()
    if run.expires_at <= now:
        raise RunExpiredError()
    return run


# Funnel counters that screening adds up across the calls of a run.
_SCREENING_COUNTERS = (
    "screened", "screen_errors", "extraction_cache_hits", "llm_calls", "input_tokens",
    "output_tokens",
)  # fmt: skip


async def add_screening_counters(
    session: AsyncSession, run_id: UUID, counters: dict[str, int]
) -> None:
    """Add to the funnel in one statement, so simultaneous calls never overwrite each other."""
    pairs = ", ".join(
        f"'{name}', COALESCE((funnel->>'{name}')::int, 0) + :{name}" for name in _SCREENING_COUNTERS
    )  # the names are constants above, never user input
    await session.execute(
        text(
            f"UPDATE search_runs SET funnel = funnel || jsonb_build_object({pairs}) "
            "WHERE id = :run_id"
        ),
        {"run_id": run_id, **{name: counters.get(name, 0) for name in _SCREENING_COUNTERS}},
    )


async def mark_run_done(session: AsyncSession, run_id: UUID) -> None:
    await session.execute(
        update(SearchRun)
        .where(SearchRun.id == run_id, SearchRun.status == "running")
        .values(status="done")
    )
