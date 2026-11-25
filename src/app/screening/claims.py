"""Claim the jobs of a run so that simultaneous `screen_batch` calls never share one.

A claim is a row moving from `pending` to `processing`. Postgres is the referee: the caller's
transaction holds a lock on the rows it picked until it commits, and `SKIP LOCKED` makes any
other call pass over them instead of waiting. Nothing is kept in memory between requests.
"""

from datetime import datetime, timedelta
from uuid import UUID

import anyio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.constants import MAX_SCREEN_ATTEMPTS
from src.db.models import RunJob


async def claim_jobs(
    session: AsyncSession,
    run_id: UUID,
    user_id: UUID,
    limit: int,
    now: datetime,
    stale_after_seconds: int,
) -> list[UUID]:
    """Take up to `limit` jobs of the run, in display order, and mark them `processing`.

    Jobs `processing` since before `now - stale_after_seconds` count as abandoned (the server
    that claimed them died) and are taken again. Each claim counts as an attempt, so a job that
    keeps crashing its worker cannot be retried forever: an abandoned claim that already used
    its attempts ends `failed` instead. The caller commits: until then the picked rows stay
    locked, which is what keeps other calls away from them.
    """
    stale_before = now - timedelta(seconds=stale_after_seconds)
    await session.execute(
        update(RunJob)
        .where(
            RunJob.run_id == run_id,
            RunJob.user_id == user_id,
            RunJob.status == "processing",
            RunJob.claimed_at < stale_before,
            RunJob.attempts >= MAX_SCREEN_ATTEMPTS,
        )
        .values(status="failed", last_error="Screening was interrupted twice (worker lost).")
    )
    picked = (
        select(RunJob.job_id)
        .where(
            RunJob.run_id == run_id,
            RunJob.user_id == user_id,
            (RunJob.status == "pending")
            | ((RunJob.status == "processing") & (RunJob.claimed_at < stale_before)),
        )
        .order_by(RunJob.position)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .cte("picked")
    )
    claimed = await session.execute(
        update(RunJob)
        .where(RunJob.run_id == run_id, RunJob.job_id.in_(select(picked.c.job_id)))
        .values(status="processing", claimed_at=now, attempts=RunJob.attempts + 1)
        .returning(RunJob.job_id, RunJob.position)
    )
    # UPDATE ... RETURNING has no order; the display order is the one to work in.
    return [job_id for job_id, _ in sorted(claimed.all(), key=lambda row: row.position)]


async def release_claims(session: AsyncSession, run_id: UUID, job_ids: list[UUID]) -> None:
    """Give back jobs that were claimed but not finished (the call was cancelled).

    The attempt is not counted: being cancelled is not the job's fault. Rows already `done` or
    `failed` are left alone, so releasing everything a call claimed is always safe.
    """
    await session.execute(
        update(RunJob)
        .where(
            RunJob.run_id == run_id,
            RunJob.job_id.in_(job_ids),
            RunJob.status == "processing",
        )
        .values(status="pending", claimed_at=None, attempts=RunJob.attempts - 1)
    )


async def release_after_cancel(
    sessions: async_sessionmaker[AsyncSession], run_id: UUID, job_ids: list[UUID]
) -> None:
    """`release_claims` in its own session, protected from the cancellation that called for it.

    A host timeout cancels the whole scope the tool runs in, and in that state every `await`
    raises again at once, so an ordinary `finally` would be cancelled before it released
    anything. The shield lets this one short cleanup finish.
    """
    if not job_ids:
        return
    with anyio.CancelScope(shield=True):
        async with sessions() as session:
            await release_claims(session, run_id, job_ids)
            await session.commit()
