"""Claims need real concurrency, so these tests commit for real (`committed_sessions`)."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.jobs.store import upsert_shared_jobs
from src.app.profile.seed import seed_sample_profile
from src.app.screening.claims import claim_jobs, release_claims
from src.db.models import RunJob, SearchRun
from tests.conftest import SAMPLE_EVIDENCE
from tests.factories import make_source_job

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
STALE_SECONDS = 300

Sessions = async_sessionmaker[AsyncSession]


async def _queue(sessions: Sessions, jobs: int) -> tuple[UUID, UUID]:
    """A committed run with `jobs` pending jobs; returns (user_id, run_id)."""
    async with sessions() as session:
        sample = json.loads(SAMPLE_EVIDENCE.read_text())
        user_id = (await seed_sample_profile(session, sample, max_job_age_days=30)).user_id
        candidates = await upsert_shared_jobs(
            session, [make_source_job(f"job-{n}") for n in range(jobs)], NOW
        )
        run = SearchRun(
            id=uuid4(), user_id=user_id, kind="search", expires_at=NOW + timedelta(hours=24)
        )
        session.add(run)
        await session.flush()
        for position, candidate in enumerate(candidates, start=1):
            session.add(
                RunJob(run_id=run.id, job_id=candidate.job_id, user_id=user_id, position=position)
            )
        await session.commit()
        return user_id, run.id


async def _claim(sessions: Sessions, user_id: UUID, run_id: UUID, limit: int, now=NOW):
    """One `screen_batch`-like call: claim, then commit so the claim becomes visible."""
    async with sessions() as session:
        claimed = await claim_jobs(session, run_id, user_id, limit, now, STALE_SECONDS)
        await session.commit()
        return claimed


async def _rows(sessions: Sessions, run_id: UUID) -> dict[UUID, RunJob]:
    async with sessions() as session:
        rows = await session.scalars(select(RunJob).where(RunJob.run_id == run_id))
        return {row.job_id: row for row in rows}


async def test_a_claim_takes_the_first_jobs_in_display_order(
    committed_sessions: Sessions,
):
    user_id, run_id = await _queue(committed_sessions, 5)

    claimed = await _claim(committed_sessions, user_id, run_id, limit=2)

    rows = await _rows(committed_sessions, run_id)
    assert [rows[job_id].position for job_id in claimed] == [1, 2]
    assert {row.status for job_id, row in rows.items() if job_id in claimed} == {"processing"}
    assert all(rows[job_id].attempts == 1 and rows[job_id].claimed_at == NOW for job_id in claimed)
    assert sum(row.status == "pending" for row in rows.values()) == 3


async def test_a_claim_in_flight_makes_another_call_skip_those_jobs(
    committed_sessions: Sessions,
):
    """The heart of SKIP LOCKED: call A has not committed yet, and call B does not wait for it."""
    user_id, run_id = await _queue(committed_sessions, 6)

    async with committed_sessions() as first, committed_sessions() as second:
        from_first = await claim_jobs(first, run_id, user_id, 3, NOW, STALE_SECONDS)
        # `first` is still open: its three rows are locked. `second` must not block on them.
        from_second = await asyncio.wait_for(
            claim_jobs(second, run_id, user_id, 3, NOW, STALE_SECONDS), timeout=5
        )
        await first.commit()
        await second.commit()

    assert len(from_first) == len(from_second) == 3
    assert set(from_first).isdisjoint(from_second)


async def test_simultaneous_calls_never_process_the_same_job(committed_sessions: Sessions):
    user_id, run_id = await _queue(committed_sessions, 20)

    batches = await asyncio.gather(
        *(_claim(committed_sessions, user_id, run_id, limit=5) for _ in range(6))
    )

    claimed = [job_id for batch in batches for job_id in batch]
    assert len(claimed) == len(set(claimed)) == 20  # nobody twice, and nothing left over


async def test_a_stale_claim_is_taken_again_but_a_fresh_one_is_not(committed_sessions: Sessions):
    user_id, run_id = await _queue(committed_sessions, 2)
    first = await _claim(committed_sessions, user_id, run_id, limit=2)  # then the server "dies"

    just_before = NOW + timedelta(seconds=STALE_SECONDS - 1)
    assert await _claim(committed_sessions, user_id, run_id, 2, now=just_before) == []

    later = NOW + timedelta(seconds=STALE_SECONDS + 1)
    again = await _claim(committed_sessions, user_id, run_id, 2, now=later)
    assert again == first
    rows = await _rows(committed_sessions, run_id)
    assert {row.attempts for row in rows.values()} == {2}  # the lost claim counted


async def test_a_job_whose_claims_keep_getting_lost_ends_failed(committed_sessions: Sessions):
    user_id, run_id = await _queue(committed_sessions, 1)
    for lost in range(2):  # two claims, each abandoned by a server that died
        at = NOW + timedelta(seconds=(STALE_SECONDS + 1) * lost)
        assert len(await _claim(committed_sessions, user_id, run_id, 1, now=at)) == 1

    third = NOW + timedelta(seconds=(STALE_SECONDS + 1) * 2)
    assert await _claim(committed_sessions, user_id, run_id, 1, now=third) == []

    (row,) = (await _rows(committed_sessions, run_id)).values()
    assert (row.status, row.attempts) == ("failed", 2)
    assert "interrupted" in row.last_error


async def test_done_and_failed_jobs_are_never_claimed(committed_sessions: Sessions):
    user_id, run_id = await _queue(committed_sessions, 3)
    rows = await _rows(committed_sessions, run_id)
    by_position = sorted(rows.values(), key=lambda row: row.position)
    async with committed_sessions() as session:
        for row, status in zip(by_position[:2], ["done", "failed"], strict=True):
            (await session.get_one(RunJob, (run_id, row.job_id))).status = status
        await session.commit()

    claimed = await _claim(committed_sessions, user_id, run_id, limit=10)

    assert claimed == [by_position[2].job_id]


async def test_another_users_run_cannot_be_claimed(committed_sessions: Sessions):
    _, run_id = await _queue(committed_sessions, 2)

    assert await _claim(committed_sessions, uuid4(), run_id, limit=10) == []


async def test_releasing_gives_the_jobs_back_without_counting_the_attempt(
    committed_sessions: Sessions,
):
    user_id, run_id = await _queue(committed_sessions, 3)
    claimed = await _claim(committed_sessions, user_id, run_id, limit=3)
    async with committed_sessions() as session:  # one of them finished before the cancel
        (await session.get_one(RunJob, (run_id, claimed[0]))).status = "done"
        await release_claims(session, run_id, claimed)
        await session.commit()

    rows = await _rows(committed_sessions, run_id)
    assert rows[claimed[0]].status == "done"
    for job_id in claimed[1:]:
        assert (rows[job_id].status, rows[job_id].attempts) == ("pending", 0)
        assert rows[job_id].claimed_at is None
