"""Screen one claimed job: extract its facts, judge eligibility, save the result at once."""

from dataclasses import dataclass, fields
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.eligibility.rules import evaluate_eligibility
from src.app.screening.extract_batch import extract_one
from src.app.screening.results import record_failure, save_verdict
from src.app.screening.screening_hash import screening_hash
from src.models.profile import Constraints


@dataclass(frozen=True)
class ScreenStats:
    """What a call did; feeds the funnel counters of the run."""

    screened: int = 0  # jobs that got a verdict
    errors: int = 0  # jobs whose extraction failed (retried or given up on, see `record_failure`)
    cache_hits: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: ScreenStats) -> ScreenStats:
        return ScreenStats(*(getattr(self, f.name) + getattr(other, f.name) for f in fields(self)))


async def screen_one(
    sessions: async_sessionmaker[AsyncSession],
    run_id: UUID,
    job_id: UUID,
    constraints: Constraints,
    now: datetime,
) -> ScreenStats:
    """Each verdict is saved as soon as it exists, in its own session: a round cut short by its
    time budget keeps every job it finished. Eligibility is plain code, so it costs nothing."""
    outcome = await extract_one(sessions, job_id)
    extracted = outcome.extracted
    async with sessions() as session:
        if extracted is None:
            await record_failure(session, run_id, job_id, outcome.error)
            await session.commit()
            return ScreenStats(errors=1)
        verdict = evaluate_eligibility(extracted.facts, constraints, outcome.declared)
        await save_verdict(session, run_id, job_id, verdict, screening_hash(constraints), now)
        await session.commit()
    if extracted.from_cache:
        return ScreenStats(screened=1, cache_hits=1)
    usage = extracted.usage
    return ScreenStats(
        screened=1, llm_calls=1, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
    )
