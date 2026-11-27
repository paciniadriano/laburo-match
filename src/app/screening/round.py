"""A screening round: workers take the run's next jobs, most relevant first, until time is up.

The user waits about 30 seconds for the first results at most, so a round is bounded by time,
not by a number of jobs: cached jobs take milliseconds and a round gets through all of them,
new ones take an LLM call each. A pool (every worker takes the next job as soon as it is free)
instead of fixed batches: nobody waits for the slowest job of a batch, and each verdict is saved
the moment it exists. When the time is up, the jobs still in flight go back to the queue; their
extraction, if it finished, is cached, so the next round does not pay for it again.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import anyio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.screening.claims import claim_jobs, release_after_cancel
from src.app.screening.screen import ScreenStats, screen_one
from src.models.profile import Constraints


@dataclass(frozen=True)
class RoundLimits:
    seconds: float  # how long the round may take new jobs
    workers: int  # jobs screened at the same time (`LLM_CONCURRENCY`)
    max_jobs: int  # a safety stop on the jobs one round may take
    stale_after_seconds: int  # claims older than this belong to a call that died


async def screen_round(
    sessions: async_sessionmaker[AsyncSession],
    run_id: UUID,
    user_id: UUID,
    constraints: Constraints,
    limits: RoundLimits,
    now: datetime,
) -> ScreenStats:
    # Real elapsed time on purpose: this is how long the user waits, not business time.
    deadline = anyio.current_time() + limits.seconds
    room = [limits.max_jobs]  # jobs the round may still take, shared by every worker
    results: list[ScreenStats] = []

    async def take_next() -> UUID | None:
        if room[0] <= 0 or anyio.current_time() >= deadline:
            return None
        room[0] -= 1  # reserved before the await, so workers together never pass `max_jobs`
        async with sessions() as session:
            claimed = await claim_jobs(session, run_id, user_id, 1, now, limits.stale_after_seconds)
            await session.commit()  # visible to other calls before the slow work begins
        if not claimed:
            room[0] = 0  # the queue is empty: every worker can stop
            return None
        return claimed[0]

    async def work(jobs: int | None = None) -> None:
        taken = 0
        while jobs is None or taken < jobs:
            job_id = await take_next()
            if job_id is None:
                return
            taken += 1
            finished = False
            try:
                with anyio.move_on_after(deadline - anyio.current_time()):
                    results.append(await screen_one(sessions, run_id, job_id, constraints, now))
                    finished = True
            finally:
                if not finished:  # time ran out, or the host cancelled the call
                    await release_after_cancel(sessions, run_id, [job_id])

    # The first job runs alone: the provider caches the shared prompt prefix only after it has
    # answered once, so jobs launched together would all pay full price for it.
    await work(jobs=1)
    async with anyio.create_task_group() as group:
        for _ in range(limits.workers):
            group.start_soon(work)
    return sum(results, ScreenStats())
