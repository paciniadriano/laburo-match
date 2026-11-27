"""Extracting one claimed job: its own session, its failures reported by class only, its cache."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.jobs.store import upsert_shared_jobs
from src.app.screening.extract_batch import extract_one
from src.db.models import Job
from src.llm import use_backend
from tests.factories import make_source_job
from tests.fakes.probe_llm import ProbeLLM

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)

Sessions = async_sessionmaker[AsyncSession]


async def _store_jobs(sessions: Sessions, count: int) -> list[UUID]:
    async with sessions() as session:
        candidates = await upsert_shared_jobs(
            session, [make_source_job(f"job-{n}", title=f"Role {n}") for n in range(count)], NOW
        )
        await session.commit()
    return [candidate.job_id for candidate in candidates]


async def test_a_failure_is_reported_by_class_and_never_raised(committed_sessions: Sessions):
    [job_id] = await _store_jobs(committed_sessions, 1)

    with use_backend(ProbeLLM(fail_for="Role 0")):
        outcome = await extract_one(committed_sessions, job_id)

    assert outcome.extracted is None
    assert outcome.error == "TimeoutError"  # the class only, never the message
    async with committed_sessions() as session:
        assert (await session.get_one(Job, job_id)).title == "Role 0"


async def test_a_failure_log_never_contains_the_error_message(committed_sessions: Sessions, caplog):
    [job_id] = await _store_jobs(committed_sessions, 1)

    with use_backend(ProbeLLM(fail_for="Role 0")), caplog.at_level("WARNING"):
        await extract_one(committed_sessions, job_id)

    logged = " ".join(f"{record.getMessage()} {record.__dict__}" for record in caplog.records)
    assert "TimeoutError" in logged
    assert "provider timed out" not in logged  # the message is where posting text could leak


async def test_a_job_extracted_once_costs_no_llm_call_the_second_time(committed_sessions: Sessions):
    [job_id] = await _store_jobs(committed_sessions, 1)
    with use_backend(ProbeLLM()):
        await extract_one(committed_sessions, job_id)

    second_time = ProbeLLM()
    with use_backend(second_time):
        outcome = await extract_one(committed_sessions, job_id)

    assert second_time.calls == 0
    assert outcome.extracted is not None and outcome.extracted.from_cache
