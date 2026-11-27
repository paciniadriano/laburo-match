"""`list_jobs` after real screening: what the user can look at, what was left out, and why."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.core import clock
from src.db.models import Profile, RunJob, User
from src.llm import use_backend
from src.tools.list_jobs import list_jobs_tool
from src.tools.screen_batch import screen_batch_tool
from tests.factories import queue_run
from tests.fakes.latam_llm import LATAM_BODY, LatamLLM

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
SETTINGS = Settings.from_env_file(None)

Sessions = async_sessionmaker[AsyncSession]


async def _screened_run(sessions: Sessions, jobs: int) -> tuple[UUID, UUID]:
    """A screened run for the sample user: every job opens to Latin America, so all eligible."""
    user_id, run_id = await queue_run(sessions, jobs, lambda n: LATAM_BODY)
    with use_backend(LatamLLM()), clock.freeze(NOW):
        await screen_batch_tool(sessions, SETTINGS, user_id, str(run_id))
    return user_id, run_id


async def _list(sessions: Sessions, user_id: UUID, **arguments: object):
    async with sessions() as session:
        with clock.freeze(NOW):
            return await list_jobs_tool(session, user_id, **arguments)  # pyright: ignore[reportArgumentType]


async def test_every_judged_job_can_be_listed_page_by_page(committed_sessions: Sessions):
    user_id, _ = await _screened_run(committed_sessions, 5)

    first = await _list(committed_sessions, user_id, limit=2)
    last = await _list(committed_sessions, user_id, limit=2, offset=4)

    assert (first.total, len(first.items), first.has_more) == (5, 2, True)
    assert "offset=2" in first.next_step_hint
    assert (len(last.items), last.has_more) == (1, False)
    assert "no more jobs" in last.next_step_hint
    assert all(item.verdict == "eligible" and item.apply_url for item in first.items)
    assert first.items[0].source == "Get on Board"  # attribution the source requires
    assert "not legal advice" in first.disclaimer


async def test_what_the_prefilter_left_out_is_listed_apart_with_its_reason(
    committed_sessions: Sessions,
):
    user_id, run_id = await _screened_run(committed_sessions, 3)
    async with committed_sessions() as session:
        await session.execute(
            update(RunJob)
            .where(RunJob.run_id == run_id, RunJob.position == 1)
            .values(prefilter_reason="office_abroad", eligibility=None)
        )
        await session.commit()

    kept = await _list(committed_sessions, user_id)
    left_out = await _list(committed_sessions, user_id, status="filtered")

    assert kept.total == 2
    assert [(i.verdict, i.reason) for i in left_out.items] == [
        ("filtered", "Hybrid or on-site, and every office is in another country.")
    ]


async def test_a_verdict_from_an_older_profile_is_marked_stale(committed_sessions: Sessions):
    user_id, _ = await _screened_run(committed_sessions, 2)
    async with committed_sessions() as session:
        profile = await session.get_one(Profile, user_id)
        profile.constraints = {**profile.constraints, "work_authorizations": ["AR", "EU"]}
        await session.commit()

    listed = await _list(committed_sessions, user_id)

    assert listed.items and all(item.stale for item in listed.items)


async def test_a_page_never_exceeds_the_limit_the_host_can_take(committed_sessions: Sessions):
    user_id, _ = await _screened_run(committed_sessions, 3)

    assert len((await _list(committed_sessions, user_id, limit=10_000)).items) == 3
    assert len((await _list(committed_sessions, user_id, limit=0)).items) == 1
    assert (await _list(committed_sessions, user_id, offset=-5)).offset == 0


async def test_another_users_jobs_are_never_listed(committed_sessions: Sessions):
    await _screened_run(committed_sessions, 3)
    async with committed_sessions() as session:
        friend = User(external_id="friend")
        session.add(friend)
        await session.flush()
        session.add(Profile(user_id=friend.id, is_complete=True, constraints={"country": "AR"}))
        await session.commit()

    listed = await _list(committed_sessions, friend.id)

    assert (listed.total, listed.items) == (0, [])
