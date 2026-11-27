"""`screen_batch`: one time-boxed round of extraction and eligibility over a run's queue.

Read it as the steps of the tool. Unlike `search_jobs` it manages its own transactions: each
claim must be committed before the slow work starts (other calls have to see it), and every
parallel worker needs a session of its own, so it receives the session factory.
"""

from uuid import UUID

import anyio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.profile.store import load_constraints
from src.app.screening.report import build_screen_result
from src.app.screening.round import RoundLimits, screen_round
from src.app.screening.screen import ScreenStats
from src.app.search.runs import add_screening_counters, load_run, mark_run_done
from src.config.settings import Settings
from src.core import clock
from src.models.screening import ScreenBatchResult


async def screen_batch_tool(
    sessions: async_sessionmaker[AsyncSession], settings: Settings, user_id: UUID, run_id: str
) -> ScreenBatchResult:
    now = clock.now()

    # 1. The run must be the user's and still usable; screening needs the user's constraints.
    async with sessions() as session:
        run = await load_run(session, user_id, run_id, now)
        constraints = await load_constraints(session, user_id)

    # 2. One round: workers take the next jobs, most relevant first, for about
    #    SCREEN_ROUND_SECONDS. Jobs left unfinished when the time is up, or when the host
    #    cancels the call, go back to the queue.
    limits = RoundLimits(
        seconds=settings.screen_round_seconds,
        workers=settings.llm_concurrency,
        max_jobs=settings.screen_max_jobs_per_call,
        stale_after_seconds=settings.claim_stale_seconds,
    )
    started = anyio.current_time()
    stats = await screen_round(sessions, run.id, user_id, constraints, limits, now)
    elapsed_ms = int((anyio.current_time() - started) * 1000)

    # 3. Record what this call did and report the best jobs judged so far.
    async with sessions() as session:
        await add_screening_counters(session, run.id, _funnel_counters(stats, elapsed_ms))
        target_roles = tuple(run.plan.get("target_roles") or ())  # what this search looked for
        result = await build_screen_result(session, run.id, target_roles)
        if result.status == "done":
            await mark_run_done(session, run.id)
        await session.commit()
    return result


def _funnel_counters(stats: ScreenStats, elapsed_ms: int) -> dict[str, int]:
    return {
        "screen_ms": elapsed_ms,  # summed over rounds: the time to tune the round and concurrency
        "screened": stats.screened,
        "screen_errors": stats.errors,
        "extraction_cache_hits": stats.cache_hits,
        "llm_calls": stats.llm_calls,
        "input_tokens": stats.input_tokens,
        "output_tokens": stats.output_tokens,
    }
