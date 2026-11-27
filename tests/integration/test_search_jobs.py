from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings
from src.core import clock
from src.core.errors import ProfileRequiredError
from src.db.models import Job, Profile, RunJob, SearchRun, User
from src.tools.search_jobs import search_jobs_tool
from tests.factories import make_source_job
from tests.fakes.fake_source import ExplodingSource, FakeSource

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
SETTINGS = Settings.from_env_file(None)


def days_ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


async def _rows(session: AsyncSession, run_id: str) -> list[RunJob]:
    result = await session.scalars(
        select(RunJob).where(RunJob.run_id == UUID(run_id)).order_by(RunJob.position)
    )
    return list(result)


async def _finish(session: AsyncSession, run_id: str) -> None:
    """Pretend `screen_batch` judged every waiting job of the run."""
    await session.execute(
        update(RunJob)
        .where(RunJob.run_id == UUID(run_id), RunJob.status == "pending")
        .values(status="done")
    )


async def test_a_search_stores_the_jobs_and_queues_the_best_titles_first(
    session: AsyncSession, user_id: UUID
):
    source = FakeSource(
        [
            make_source_job("designer", "Product Designer"),
            make_source_job("front", "Frontend Engineer"),
            make_source_job("back", "Backend Engineer"),
        ]
    )

    with clock.freeze(NOW):
        summary = await search_jobs_tool(session, [source], SETTINGS, user_id)

    assert (summary.fetched, summary.to_screen, summary.over_cap) == (3, 3, 0)
    assert summary.by_source == {"getonbrd": 3}
    assert "screen_batch" in summary.next_step_hint
    rows = await _rows(session, summary.run_id)
    titles = [(await session.get_one(Job, row.job_id)).title for row in rows]
    assert titles == ["Frontend Engineer", "Backend Engineer", "Product Designer"]
    assert {row.status for row in rows} == {"pending"}
    assert [row.position for row in rows] == [1, 2, 3]


async def test_the_plan_and_funnel_are_stored_in_the_run_for_audit(
    session: AsyncSession, user_id: UUID
):
    with clock.freeze(NOW):
        summary = await search_jobs_tool(
            session, [FakeSource([make_source_job("a")])], SETTINGS, user_id
        )

    run = await session.get_one(SearchRun, UUID(summary.run_id))
    assert run.kind == "search" and run.status == "running"
    assert run.plan["sources"] == {"getonbrd": {"categories": ["programming"]}}
    assert run.funnel["fetched"] == 1
    assert run.expires_at == NOW + timedelta(hours=24)


async def test_a_second_search_skips_what_the_user_already_judged(
    session: AsyncSession, user_id: UUID
):
    source = FakeSource([make_source_job("a"), make_source_job("b")])
    with clock.freeze(NOW):
        first = await search_jobs_tool(session, [source], SETTINGS, user_id)
        await _finish(session, first.run_id)
        second = await search_jobs_tool(session, [source], SETTINGS, user_id)

    assert (second.fetched, second.already_seen, second.to_screen) == (2, 2, 0)
    assert "No new jobs" in second.next_step_hint


async def test_old_jobs_are_discarded_but_recorded_with_their_reason(
    session: AsyncSession, user_id: UUID
):
    source = FakeSource(
        [
            make_source_job("fresh", posted_at=days_ago(2)),
            make_source_job("old", posted_at=days_ago(45)),
        ]
    )

    with clock.freeze(NOW):
        summary = await search_jobs_tool(session, [source], SETTINGS, user_id)

    assert summary.discarded == {"too_old": 1}
    assert summary.to_screen == 1
    rows = await _rows(session, summary.run_id)
    discarded = [row for row in rows if row.prefilter_reason]
    assert [(row.status, row.prefilter_reason) for row in discarded] == [("done", "too_old")]
    assert discarded[0].screened_at == NOW


async def test_jobs_over_the_cap_are_left_for_the_next_search(session: AsyncSession, user_id: UUID):
    jobs = [make_source_job(f"job-{n}", posted_at=days_ago(n)) for n in range(1, 6)]
    source = FakeSource(jobs)

    with clock.freeze(NOW):
        first = await search_jobs_tool(session, [source], SETTINGS, user_id, max_new=2)
        await _finish(session, first.run_id)
        second = await search_jobs_tool(session, [source], SETTINGS, user_id, max_new=10)

    assert (first.to_screen, first.over_cap) == (2, 3)
    assert "3 more new jobs" in first.next_step_hint
    assert "more new jobs" not in second.next_step_hint
    # The three that did not fit were never given a row, so they are still new.
    assert (second.already_seen, second.to_screen, second.over_cap) == (2, 3, 0)
    assert await session.scalar(select(func.count()).select_from(RunJob)) == 5  # each job once


async def test_the_server_cap_limits_what_the_caller_asks_for(session: AsyncSession, user_id: UUID):
    source = FakeSource([make_source_job(f"job-{n}") for n in range(5)])
    capped = SETTINGS.model_copy(update={"max_new_jobs_per_search": 2})

    with clock.freeze(NOW):
        summary = await search_jobs_tool(session, [source], capped, user_id, max_new=1000)

    assert summary.to_screen == 2


async def test_a_job_seen_again_is_updated_in_place_and_keeps_its_identity(
    session: AsyncSession, user_id: UUID
):
    with clock.freeze(NOW):
        await search_jobs_tool(
            session, [FakeSource([make_source_job("a", body="old text")])], SETTINGS, user_id
        )
    before = (await session.execute(select(Job))).scalar_one()
    first_hash, job_id = before.content_hash, before.id

    later = NOW + timedelta(days=1)
    with clock.freeze(later):
        await search_jobs_tool(
            session, [FakeSource([make_source_job("a", body="new text")])], SETTINGS, user_id
        )

    after = (
        await session.execute(select(Job).execution_options(populate_existing=True))
    ).scalar_one()
    assert after.id == job_id  # same job, so cached facts and decisions stay attached
    assert after.content_hash != first_hash  # the cache for the old text no longer applies
    assert after.raw_text == "new text"
    assert (after.first_seen_at, after.last_seen_at) == (NOW, later)


async def test_the_same_job_twice_in_one_batch_is_stored_once(session: AsyncSession, user_id: UUID):
    source = FakeSource([make_source_job("dup"), make_source_job("dup")])

    with clock.freeze(NOW):
        summary = await search_jobs_tool(session, [source], SETTINGS, user_id)

    assert summary.fetched == 1


async def test_a_source_warning_reaches_the_summary_and_a_crashing_source_does_not_stop_the_search(
    session: AsyncSession, user_id: UUID
):
    good = FakeSource([make_source_job("a")], warnings=["Get on Board did not answer in time."])

    with clock.freeze(NOW):
        summary = await search_jobs_tool(session, [good, ExplodingSource()], SETTINGS, user_id)

    assert summary.to_screen == 1
    assert summary.warnings == [
        "Get on Board did not answer in time.",
        "explosive: unexpected error, skipped.",
    ]


async def test_an_incomplete_profile_is_refused(session: AsyncSession, user_id: UUID):
    profile = await session.get_one(Profile, user_id)
    profile.is_complete = False
    await session.flush()

    with pytest.raises(ProfileRequiredError):
        await search_jobs_tool(session, [FakeSource([])], SETTINGS, user_id)


async def test_a_user_without_a_profile_is_refused(session: AsyncSession):
    nobody = User(external_id="nobody")
    session.add(nobody)
    await session.flush()

    with pytest.raises(ProfileRequiredError):
        await search_jobs_tool(session, [FakeSource([])], SETTINGS, nobody.id)


async def test_each_user_has_their_own_new_jobs(session: AsyncSession, user_id: UUID):
    other = User(external_id="friend")
    session.add(other)
    await session.flush()
    session.add(
        Profile(
            user_id=other.id, is_complete=True, preferences={"target_roles": ["Frontend Engineer"]}
        )
    )
    await session.flush()
    source = FakeSource([make_source_job("a"), make_source_job("b")])

    with clock.freeze(NOW):
        mine = await search_jobs_tool(session, [source], SETTINGS, user_id)
        theirs = await search_jobs_tool(session, [source], SETTINGS, other.id)

    # The jobs table is shared, but what each person has already seen is not.
    assert (mine.to_screen, theirs.to_screen, theirs.already_seen) == (2, 2, 0)
    assert await session.scalar(select(func.count()).select_from(Job)) == 2


async def _row_states(session: AsyncSession, run_id: str) -> list[str]:
    return [row.status for row in await _rows(session, run_id)]


async def test_jobs_an_unfinished_run_left_waiting_move_to_the_new_run(
    session: AsyncSession, user_id: UUID
):
    source = FakeSource([make_source_job(f"job-{n}") for n in range(3)])

    with clock.freeze(NOW):
        first = await search_jobs_tool(session, [source], SETTINGS, user_id)
        second = await search_jobs_tool(session, [source], SETTINGS, user_id)

    assert (second.already_seen, second.carried_over, second.to_screen) == (0, 3, 3)
    assert "left unscreened by an earlier search" in second.next_step_hint
    # Each job waits in one run only, so no screen_batch can process it twice.
    assert await _rows(session, first.run_id) == []
    assert await _row_states(session, second.run_id) == ["pending"] * 3


async def test_a_job_a_live_call_is_processing_is_left_alone(session: AsyncSession, user_id: UUID):
    source = FakeSource([make_source_job("a"), make_source_job("b")])

    with clock.freeze(NOW):
        first = await search_jobs_tool(session, [source], SETTINGS, user_id)
        taken = (await _rows(session, first.run_id))[0]
        taken.status, taken.claimed_at = "processing", NOW
        await session.flush()
        second = await search_jobs_tool(session, [source], SETTINGS, user_id)

    assert (second.already_seen, second.carried_over, second.to_screen) == (1, 1, 1)
    assert await _row_states(session, first.run_id) == ["processing"]


async def test_a_job_whose_call_died_is_carried_over(session: AsyncSession, user_id: UUID):
    source = FakeSource([make_source_job("a")])

    with clock.freeze(NOW):
        first = await search_jobs_tool(session, [source], SETTINGS, user_id)
        row = (await _rows(session, first.run_id))[0]
        row.status = "processing"
        row.claimed_at = NOW - timedelta(seconds=SETTINGS.claim_stale_seconds + 1)
        await session.flush()
        second = await search_jobs_tool(session, [source], SETTINGS, user_id)

    assert (second.already_seen, second.carried_over, second.to_screen) == (0, 1, 1)


async def test_a_job_that_failed_screening_is_not_taken_again(session: AsyncSession, user_id: UUID):
    source = FakeSource([make_source_job("a")])

    with clock.freeze(NOW):
        first = await search_jobs_tool(session, [source], SETTINGS, user_id)
        (await _rows(session, first.run_id))[0].status = "failed"
        await session.flush()
        second = await search_jobs_tool(session, [source], SETTINGS, user_id)

    assert (second.already_seen, second.carried_over, second.to_screen) == (1, 0, 0)


async def test_unfinished_jobs_over_the_cap_stay_where_they_are(
    session: AsyncSession, user_id: UUID
):
    jobs = [make_source_job(f"job-{n}", posted_at=days_ago(n)) for n in range(1, 4)]
    source = FakeSource(jobs)

    with clock.freeze(NOW):
        first = await search_jobs_tool(session, [source], SETTINGS, user_id)
        second = await search_jobs_tool(session, [source], SETTINGS, user_id, max_new=1)

    assert (second.carried_over, second.to_screen, second.over_cap) == (1, 1, 2)
    # Only the job the new run took moved; the other two still wait in the first run.
    assert len(await _rows(session, first.run_id)) == 2
    assert len(await _rows(session, second.run_id)) == 1
