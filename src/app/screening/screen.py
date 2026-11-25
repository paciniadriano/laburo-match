"""Screen the jobs a call has claimed: extract their facts, judge eligibility, save the result."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.eligibility.rules import evaluate_eligibility
from src.app.screening.extract_batch import extract_jobs
from src.app.screening.results import record_failure, save_verdict
from src.app.screening.screening_hash import screening_hash
from src.models.profile import Constraints


@dataclass(frozen=True)
class ScreenStats:
    """What one call did; feeds the funnel counters of the run."""

    screened: int = 0  # jobs that got a verdict
    errors: int = 0  # jobs whose extraction failed (retried or given up on, see `record_failure`)
    cache_hits: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


async def screen_jobs(
    sessions: async_sessionmaker[AsyncSession],
    run_id: UUID,
    job_ids: list[UUID],
    constraints: Constraints,
    concurrency: int,
    now: datetime,
) -> ScreenStats:
    """The slow step (LLM) runs first, in parallel; the verdicts are then saved in one commit.

    Eligibility is plain code, so it costs nothing to keep it after the extraction instead of
    inside each parallel task.
    """
    outcomes = await extract_jobs(sessions, job_ids, concurrency)
    current_hash = screening_hash(constraints)
    screened = errors = cache_hits = llm_calls = input_tokens = output_tokens = 0

    async with sessions() as session:
        for outcome in outcomes:
            extracted = outcome.extracted
            if extracted is None:
                errors += 1
                await record_failure(session, run_id, outcome.job_id, outcome.error)
                continue
            verdict = evaluate_eligibility(extracted.facts, constraints)
            await save_verdict(session, run_id, outcome.job_id, verdict, current_hash, now)
            screened += 1
            if extracted.from_cache:
                cache_hits += 1
            else:
                llm_calls += 1
                input_tokens += extracted.usage.input_tokens
                output_tokens += extracted.usage.output_tokens
        await session.commit()

    return ScreenStats(screened, errors, cache_hits, llm_calls, input_tokens, output_tokens)
