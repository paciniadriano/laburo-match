"""A screening round: a pool of workers, most relevant jobs first, bounded by time."""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.screening.round import RoundLimits, screen_round
from src.app.screening.screen import ScreenStats
from src.app.screening.screening_hash import screening_hash
from src.db.models import Job, Profile, RunJob
from src.llm import use_backend
from src.models.profile import Constraints
from tests.factories import queue_run
from tests.fakes.latam_llm import LATAM_BODY, LatamLLM
from tests.fakes.probe_llm import ProbeLLM

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)

Sessions = async_sessionmaker[AsyncSession]


@pytest.fixture(autouse=True)
def _model() -> Iterator[None]:
    """Unless a test says otherwise, the model opens every job to Latin America."""
    with use_backend(LatamLLM()):
        yield


async def _round(
    sessions: Sessions,
    user_id: UUID,
    run_id: UUID,
    seconds: float = 30,
    workers: int = 2,
    max_jobs: int = 100,
) -> ScreenStats:
    async with sessions() as session:
        profile = await session.get_one(Profile, user_id)
    constraints = Constraints.model_validate(profile.constraints)
    limits = RoundLimits(seconds, workers, max_jobs, stale_after_seconds=300)
    return await screen_round(sessions, run_id, user_id, constraints, limits, NOW)


async def _rows(sessions: Sessions, run_id: UUID) -> dict[str, RunJob]:
    """The run's rows by job title."""
    async with sessions() as session:
        rows = await session.execute(
            select(Job.title, RunJob)
            .join(RunJob, RunJob.job_id == Job.id)
            .where(RunJob.run_id == run_id)
        )
        return {title: row for title, row in rows.all()}


async def test_screened_jobs_are_done_with_their_verdict_and_the_profile_fingerprint(
    committed_sessions: Sessions,
):
    user_id, run_id = await queue_run(committed_sessions, 3, lambda n: LATAM_BODY)

    stats = await _round(committed_sessions, user_id, run_id)

    assert (stats.screened, stats.errors, stats.llm_calls) == (3, 0, 3)
    assert (stats.input_tokens, stats.output_tokens) == (30, 6)
    async with committed_sessions() as session:
        profile = await session.get_one(Profile, user_id)
    expected_hash = screening_hash(Constraints.model_validate(profile.constraints))
    for row in (await _rows(committed_sessions, run_id)).values():
        assert (row.status, row.eligibility) == ("done", "eligible")
        assert row.screening_hash == expected_hash
        assert row.screened_at == NOW and row.claimed_at is None
        assert row.eligibility_quotes == ["Remote within Latin America"]


async def test_a_failing_job_gets_one_more_try_and_then_ends_failed(
    committed_sessions: Sessions,
):
    user_id, run_id = await queue_run(committed_sessions, 3, lambda n: LATAM_BODY)

    with use_backend(LatamLLM(failing_titles=("Role 1",))):
        stats = await _round(committed_sessions, user_id, run_id)
    rows = await _rows(committed_sessions, run_id)

    assert (stats.screened, stats.errors) == (2, 2)  # the others were not affected
    assert (rows["Role 1"].status, rows["Role 1"].attempts) == ("failed", 2)
    assert rows["Role 1"].last_error == "TimeoutError"
    assert rows["Role 0"].status == rows["Role 2"].status == "done"


async def test_a_finished_job_is_never_screened_again(committed_sessions: Sessions):
    user_id, run_id = await queue_run(committed_sessions, 2, lambda n: LATAM_BODY)
    await _round(committed_sessions, user_id, run_id)

    assert await _round(committed_sessions, user_id, run_id) == ScreenStats()


async def test_the_first_job_runs_alone_and_then_the_workers_share_the_rest(
    committed_sessions: Sessions,
):
    user_id, run_id = await queue_run(committed_sessions, 10)
    probe = ProbeLLM()

    with use_backend(probe):
        stats = await _round(committed_sessions, user_id, run_id, workers=3)

    assert probe.calls_started_while_first_waited == 1  # nobody else started until it answered
    assert probe.max_in_flight == 3  # parallel, but never beyond the number of workers
    assert stats.screened == 10


async def test_when_the_time_is_up_unfinished_jobs_go_back_to_the_queue_uncounted(
    committed_sessions: Sessions,
):
    user_id, run_id = await queue_run(committed_sessions, 10, lambda n: LATAM_BODY)

    with use_backend(LatamLLM(delay=0.2)):
        stats = await _round(committed_sessions, user_id, run_id, seconds=0.5, workers=2)
    rows = (await _rows(committed_sessions, run_id)).values()

    assert 0 < stats.screened < 10  # some were judged, the round did not wait for the rest
    assert not [row for row in rows if row.status == "processing"]  # nothing left claimed
    waiting = [row for row in rows if row.status == "pending"]
    assert waiting and all(
        row.attempts == 0 for row in waiting
    )  # running out of time is no failure


async def test_jobs_already_extracted_all_fit_in_one_round_even_with_a_slow_model(
    committed_sessions: Sessions,
):
    _, first_run = await queue_run(committed_sessions, 6, lambda n: LATAM_BODY)
    user_id, second_run = await queue_run(committed_sessions, 6, lambda n: LATAM_BODY)
    await _round(committed_sessions, user_id, first_run)  # fills the extraction cache

    with use_backend(LatamLLM(delay=5)):  # a call would blow the budget
        stats = await _round(committed_sessions, user_id, second_run, seconds=1)

    assert (stats.screened, stats.cache_hits, stats.llm_calls) == (6, 6, 0)


async def test_a_round_never_takes_more_jobs_than_its_safety_limit(committed_sessions: Sessions):
    user_id, run_id = await queue_run(committed_sessions, 8, lambda n: LATAM_BODY)

    stats = await _round(committed_sessions, user_id, run_id, workers=4, max_jobs=3)

    assert stats.screened == 3
