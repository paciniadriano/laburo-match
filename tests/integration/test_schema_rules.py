"""The database itself enforces the rules the design relies on."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Job, RunJob, SearchRun, User

NOW = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)


def make_user(name: str) -> User:
    return User(external_id=name)


def make_run(user: User) -> SearchRun:
    return SearchRun(user_id=user.id, kind="search", expires_at=NOW)


def make_job(external_id: str, owner: User | None = None, content_hash: str = "h") -> Job:
    return Job(
        source="getonbrd" if owner is None else "pasted",
        external_id=external_id,
        owner_user_id=owner.id if owner else None,
        title="Frontend Engineer",
        raw_text="text",
        content_hash=content_hash,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


async def test_run_job_cannot_claim_another_users_run(session: AsyncSession):
    ana, bob = make_user("ana"), make_user("bob")
    session.add_all([ana, bob])
    await session.flush()
    run = make_run(ana)
    job = make_job("1")
    session.add_all([run, job])
    await session.flush()

    session.add(RunJob(run_id=run.id, job_id=job.id, user_id=bob.id, position=1))
    with pytest.raises(IntegrityError, match="fk_run_jobs_run_id_user_id_search_runs"):
        await session.flush()


async def test_run_job_of_the_runs_owner_is_accepted(session: AsyncSession):
    ana = make_user("ana")
    session.add(ana)
    await session.flush()
    run, job = make_run(ana), make_job("1")
    session.add_all([run, job])
    await session.flush()

    session.add(RunJob(run_id=run.id, job_id=job.id, user_id=ana.id, position=1))
    await session.flush()


async def test_invalid_status_is_rejected(session: AsyncSession):
    ana = make_user("ana")
    session.add(ana)
    await session.flush()
    run, job = make_run(ana), make_job("1")
    session.add_all([run, job])
    await session.flush()

    session.add(
        RunJob(run_id=run.id, job_id=job.id, user_id=ana.id, position=1, status="procesando")
    )
    with pytest.raises(IntegrityError, match="ck_run_jobs_status"):
        await session.flush()


async def test_shared_job_is_unique_per_source_and_external_id(session: AsyncSession):
    session.add(make_job("same"))
    await session.flush()

    session.add(make_job("same"))
    with pytest.raises(IntegrityError, match="uq_jobs_source_external_id_shared"):
        await session.flush()


async def test_two_users_can_paste_the_same_text_but_not_twice_each(session: AsyncSession):
    ana, bob = make_user("ana"), make_user("bob")
    session.add_all([ana, bob])
    await session.flush()

    session.add_all([make_job("p1", ana, "same-text"), make_job("p2", bob, "same-text")])
    await session.flush()  # private to each owner: no clash

    session.add(make_job("p3", ana, "same-text"))
    with pytest.raises(IntegrityError, match="uq_jobs_owner_user_id_content_hash_pasted"):
        await session.flush()


async def test_deleting_a_user_cascades_to_their_runs(session: AsyncSession):
    ana = make_user("ana")
    session.add(ana)
    await session.flush()
    run = make_run(ana)
    session.add(run)
    await session.flush()

    await session.delete(ana)
    await session.flush()

    # Ask the database, not `session.get()`: that one answers from the session's own memory.
    remaining = await session.scalar(select(func.count()).select_from(SearchRun))
    assert remaining == 0
