"""`screen_batch`: extract, judge eligibility and save, for the next jobs of a run.

Read it as the steps of the tool. Unlike `search_jobs` it manages its own transactions: the
claim must be committed before the slow work starts (other calls have to see it), and every
parallel task needs a session of its own, so it receives the session factory.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.profile.store import load_constraints
from src.app.screening.claims import claim_jobs, release_after_cancel
from src.app.screening.report import build_screen_result
from src.app.screening.screen import ScreenStats, screen_jobs
from src.app.search.runs import add_screening_counters, load_run, mark_run_done
from src.config.settings import Settings
from src.core import clock
from src.models.screening import ScreenBatchResult


async def screen_batch(
    sessions: async_sessionmaker[AsyncSession], settings: Settings, user_id: UUID, run_id: str
) -> ScreenBatchResult:
    now = clock.now()

    # 1. The run must be the user's and still usable; screening needs the user's constraints.
    async with sessions() as session:
        run = await load_run(session, user_id, run_id, now)
        constraints = await load_constraints(session, user_id)

    # 2. Claim the next jobs and screen them. If the call is cancelled (the host gave up),
    #    whatever it claimed but did not finish goes back to the queue.
    claimed: list[UUID] = []
    stats = ScreenStats()
    try:
        async with sessions() as session:
            claimed = await claim_jobs(
                session, run.id, user_id, settings.screen_max_jobs_per_call, now,
                settings.claim_stale_seconds,
            )  # fmt: skip
            await session.commit()  # visible to other calls before the slow work begins
        if claimed:
            stats = await screen_jobs(
                sessions, run.id, claimed, constraints, settings.llm_concurrency, now
            )
    finally:
        await release_after_cancel(sessions, run.id, claimed)

    # 3. Record what this call did and report: progress, or the shortlist if nothing remains.
    async with sessions() as session:
        await add_screening_counters(session, run.id, _funnel_counters(stats))
        result = await build_screen_result(session, run.id)
        if result.status == "done":
            await mark_run_done(session, run.id)
        await session.commit()
    return result


def _funnel_counters(stats: ScreenStats) -> dict[str, int]:
    return {
        "screened": stats.screened,
        "screen_errors": stats.errors,
        "extraction_cache_hits": stats.cache_hits,
        "llm_calls": stats.llm_calls,
        "input_tokens": stats.input_tokens,
        "output_tokens": stats.output_tokens,
    }
