import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.jobs.store import upsert_shared_jobs
from src.app.screening.extract_batch import extract_jobs
from src.db.models import Job
from src.llm import use_backend
from src.llm.backend import BackendResponse, Usage
from src.llm.messages import Message
from src.llm.tasks import LLMTask
from tests.factories import make_facts, make_source_job

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)

Sessions = async_sessionmaker[AsyncSession]


class ProbeLLM:
    """A model that answers slowly and records how many calls were running at once."""

    def __init__(self, fail_for: str = "") -> None:
        self.fail_for = fail_for
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls_started_while_first_waited = 0
        self.calls = 0

    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse:
        self.calls += 1
        self.in_flight += 1
        if self.calls == 1:
            await asyncio.sleep(0.05)  # long enough for a wrongly launched neighbour to start
            self.calls_started_while_first_waited = self.calls
        else:
            await asyncio.sleep(0.02)
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.in_flight -= 1
        if self.fail_for and self.fail_for in messages[-1][1]:
            raise TimeoutError("provider timed out")
        return BackendResponse(parsed=make_facts(), usage=Usage(input_tokens=10, output_tokens=2))


async def _store_jobs(sessions: Sessions, count: int) -> list[UUID]:
    async with sessions() as session:
        candidates = await upsert_shared_jobs(
            session, [make_source_job(f"job-{n}", title=f"Role {n}") for n in range(count)], NOW
        )
        await session.commit()
    return [candidate.job_id for candidate in candidates]


async def test_every_job_gets_an_outcome_in_the_order_given(committed_sessions: Sessions):
    job_ids = await _store_jobs(committed_sessions, 6)

    with use_backend(ProbeLLM()):
        outcomes = await extract_jobs(committed_sessions, job_ids, concurrency=3)

    assert [outcome.job_id for outcome in outcomes] == job_ids
    assert all(outcome.extracted and not outcome.extracted.from_cache for outcome in outcomes)


async def test_the_first_job_runs_alone_and_the_rest_respect_the_limit(
    committed_sessions: Sessions,
):
    job_ids = await _store_jobs(committed_sessions, 10)
    probe = ProbeLLM()

    with use_backend(probe):
        await extract_jobs(committed_sessions, job_ids, concurrency=3)

    assert probe.calls_started_while_first_waited == 1  # nobody else started until it answered
    assert probe.max_in_flight == 3  # parallel, but never beyond the limit


async def test_a_failing_job_does_not_stop_the_others(committed_sessions: Sessions):
    job_ids = await _store_jobs(committed_sessions, 4)

    with use_backend(ProbeLLM(fail_for="Role 2")):
        outcomes = await extract_jobs(committed_sessions, job_ids, concurrency=2)

    failed = [outcome for outcome in outcomes if outcome.extracted is None]
    assert len(failed) == 1
    async with committed_sessions() as session:
        assert (await session.get_one(Job, failed[0].job_id)).title == "Role 2"
    assert failed[0].error == "TimeoutError"  # the class only, never the message
    assert sum(outcome.extracted is not None for outcome in outcomes) == 3


async def test_cached_jobs_cost_no_llm_calls(committed_sessions: Sessions):
    job_ids = await _store_jobs(committed_sessions, 5)
    with use_backend(ProbeLLM()):
        await extract_jobs(committed_sessions, job_ids, concurrency=3)

    second_time = ProbeLLM()
    with use_backend(second_time):
        outcomes = await extract_jobs(committed_sessions, job_ids, concurrency=3)

    assert second_time.calls == 0
    assert all(outcome.extracted and outcome.extracted.from_cache for outcome in outcomes)


async def test_an_empty_list_does_nothing(committed_sessions: Sessions):
    assert await extract_jobs(committed_sessions, [], concurrency=3) == []
