import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import anyio
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.screening.report import build_screen_result
from src.config.settings import Settings
from src.core import clock
from src.core.errors import RunExpiredError, RunNotFoundError
from src.db.models import RunJob, SearchRun
from src.llm import use_backend
from src.models.screening import ScreenBatchResult
from src.tools.screen_batch import screen_batch_tool
from tests.factories import queue_run
from tests.fakes.latam_llm import LATAM_BODY, LatamLLM

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
SETTINGS = Settings.from_env_file(None).model_copy(
    update={"screen_max_jobs_per_call": 2, "llm_concurrency": 2}
)

Sessions = async_sessionmaker[AsyncSession]


async def _call(sessions: Sessions, user_id: UUID, run_id: UUID) -> ScreenBatchResult:
    with clock.freeze(NOW):
        return await screen_batch_tool(sessions, SETTINGS, user_id, str(run_id))


async def _rows(sessions: Sessions, run_id: UUID) -> list[RunJob]:
    async with sessions() as session:
        rows = await session.scalars(select(RunJob).where(RunJob.run_id == run_id))
        return list(rows)


async def test_every_call_shows_the_best_jobs_so_far_and_the_last_one_says_it_is_done(
    committed_sessions: Sessions,
):
    user_id, run_id = await queue_run(committed_sessions, 5, lambda n: LATAM_BODY)
    model = LatamLLM()

    with use_backend(model):
        first = await _call(committed_sessions, user_id, run_id)
        second = await _call(committed_sessions, user_id, run_id)
        last = await _call(committed_sessions, user_id, run_id)

    # The safety limit of 2 jobs per round stands in for the time budget here.
    assert (first.status, first.processed, first.remaining) == ("partial", 2, 3)
    assert (second.status, second.processed, second.remaining) == ("partial", 4, 1)
    assert (len(first.shortlist), len(second.shortlist)) == (2, 4)  # results every round
    assert "3 jobs are not checked yet" in first.next_step_hint
    assert first.disclaimer  # an estimate, also when partial
    assert (last.status, last.processed, last.remaining, last.failed) == ("done", 5, 0, 0)
    assert len(last.shortlist) == 5 and last.eligible_total == 5
    assert "not legal advice" in last.disclaimer
    assert model.calls == 5  # each job was extracted once, whichever call screened it
    async with committed_sessions() as session:
        run = await session.get_one(SearchRun, run_id)
    assert run.status == "done"
    assert (run.funnel["screened"], run.funnel["llm_calls"]) == (5, 5)
    assert (run.funnel["input_tokens"], run.funnel["output_tokens"]) == (50, 10)
    assert run.funnel["screen_ms"] >= 0  # measured, to tune the round and the concurrency


async def test_the_shortlist_puts_eligible_first_and_is_capped(committed_sessions: Sessions):
    # Even jobs quote their restriction (eligible); odd ones do not, so it is only inferred.
    user_id, run_id = await queue_run(
        committed_sessions, 12, lambda n: LATAM_BODY if n % 2 == 0 else {}
    )
    settings = SETTINGS.model_copy(update={"screen_max_jobs_per_call": 15})

    with use_backend(LatamLLM()), clock.freeze(NOW):
        result = await screen_batch_tool(committed_sessions, settings, user_id, str(run_id))

    assert result.status == "done"
    assert (result.eligible_total, result.doubtful_total) == (6, 6)
    assert len(result.shortlist) == 10  # SHORTLIST_SIZE
    kinds = [card.eligibility for card in result.shortlist]
    assert kinds == ["eligible"] * 6 + ["doubtful"] * 4
    card = result.shortlist[0]
    assert card.source == "Get on Board" and card.apply_url.startswith("https://")
    assert card.quotes == ["Remote within Latin America"]


async def test_discards_and_not_eligible_jobs_are_counted_by_reason(committed_sessions: Sessions):
    user_id, run_id = await queue_run(committed_sessions, 3, lambda n: LATAM_BODY)
    async with committed_sessions() as session:
        rows = list(await session.scalars(select(RunJob).order_by(RunJob.position)))
        rows[0].prefilter_reason, rows[0].status = "too_old", "done"
        rows[1].status, rows[1].eligibility = "done", "not_eligible"
        rows[2].status, rows[2].eligibility = "done", "doubtful"
        rows[2].profile_questions = ["Do you have US work authorization?"]
        await session.commit()

    async with committed_sessions() as session:
        result = await build_screen_result(session, run_id)

    assert result.discarded == {"too_old": 1, "not_eligible": 1}
    assert result.processed == 2  # the prefilter discard was never screened
    assert result.profile_questions == ["Do you have US work authorization?"]
    assert [card.eligibility for card in result.shortlist] == ["doubtful"]


async def test_two_simultaneous_calls_never_process_the_same_job(committed_sessions: Sessions):
    user_id, run_id = await queue_run(committed_sessions, 6, lambda n: LATAM_BODY)
    settings = SETTINGS.model_copy(update={"screen_max_jobs_per_call": 3})
    model = LatamLLM(delay=0.05)

    with use_backend(model), clock.freeze(NOW):
        await asyncio.gather(
            *(
                screen_batch_tool(committed_sessions, settings, user_id, str(run_id))
                for _ in range(2)
            )
        )

    assert model.calls == 6  # a job screened twice would show up as an extra model call
    assert {row.status for row in await _rows(committed_sessions, run_id)} == {"done"}


async def test_a_cancelled_call_gives_its_claims_back(committed_sessions: Sessions):
    user_id, run_id = await queue_run(committed_sessions, 4, lambda n: LATAM_BODY)
    model = LatamLLM(delay=30)  # the host gives up long before the model answers

    with use_backend(model):
        call = asyncio.create_task(_call(committed_sessions, user_id, run_id))
        await asyncio.wait_for(model.started.wait(), timeout=5)
        claimed_while_running = sum(
            row.status == "processing" for row in await _rows(committed_sessions, run_id)
        )
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call

    rows = await _rows(committed_sessions, run_id)
    assert claimed_while_running == 1  # the first job runs alone, to warm the prompt cache
    assert {(row.status, row.attempts) for row in rows} == {("pending", 0)}


async def test_cancelling_the_way_the_server_does_still_releases_the_claims(
    committed_sessions: Sessions,
):
    """FastMCP runs on anyio, whose cancellation is not one-shot like `Task.cancel()`: inside a
    cancelled scope every `await` raises again, so the release only works if it is shielded."""
    user_id, run_id = await queue_run(committed_sessions, 4, lambda n: LATAM_BODY)
    model = LatamLLM(delay=30)
    scope = anyio.CancelScope()

    async def run_tool() -> None:
        with scope:
            await _call(committed_sessions, user_id, run_id)

    async def cancel_when_the_model_is_called() -> None:
        await model.started.wait()
        scope.cancel()

    with use_backend(model):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(run_tool)
            tasks.start_soon(cancel_when_the_model_is_called)

    rows = await _rows(committed_sessions, run_id)
    assert {(row.status, row.attempts) for row in rows} == {("pending", 0)}


async def test_a_job_failing_twice_ends_failed_and_the_run_still_finishes(
    committed_sessions: Sessions,
):
    user_id, run_id = await queue_run(committed_sessions, 3, lambda n: LATAM_BODY)
    settings = SETTINGS.model_copy(update={"screen_max_jobs_per_call": 10})

    with use_backend(LatamLLM(failing_titles=("Role 1",))), clock.freeze(NOW):
        last = await screen_batch_tool(committed_sessions, settings, user_id, str(run_id))

    # The retry happens inside the same round, so one call is enough to settle it.
    assert (last.status, last.processed, last.failed, last.remaining) == ("done", 2, 1, 0)
    assert len(last.shortlist) == 2


async def test_a_finished_run_can_be_asked_again_without_new_work(committed_sessions: Sessions):
    user_id, run_id = await queue_run(committed_sessions, 2, lambda n: LATAM_BODY)
    model = LatamLLM()
    with use_backend(model):
        first = await _call(committed_sessions, user_id, run_id)
        again = await _call(committed_sessions, user_id, run_id)

    assert first.status == again.status == "done"
    assert first.shortlist == again.shortlist
    assert model.calls == 2


async def test_another_users_run_and_garbage_ids_are_not_found(committed_sessions: Sessions):
    _, run_id = await queue_run(committed_sessions, 1)
    stranger = uuid4()

    with pytest.raises(RunNotFoundError):
        await _call(committed_sessions, stranger, run_id)
    with pytest.raises(RunNotFoundError):
        with clock.freeze(NOW):
            await screen_batch_tool(committed_sessions, SETTINGS, stranger, "3")  # a position


async def test_an_expired_run_is_refused(committed_sessions: Sessions):
    user_id, run_id = await queue_run(committed_sessions, 1)

    with pytest.raises(RunExpiredError), clock.freeze(NOW + timedelta(hours=25)):
        await screen_batch_tool(committed_sessions, SETTINGS, user_id, str(run_id))
