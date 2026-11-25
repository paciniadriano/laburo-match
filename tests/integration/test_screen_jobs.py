from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.screening.claims import claim_jobs
from src.app.screening.screen import ScreenStats, screen_jobs
from src.app.screening.screening_hash import screening_hash
from src.db.models import Job, Profile, RunJob
from src.llm import use_backend
from src.llm.backend import BackendResponse, Usage
from src.llm.messages import Message
from src.llm.tasks import LLMTask
from src.models.profile import Constraints
from tests.factories import make_facts, make_restriction, queue_run

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
STALE_SECONDS = 300

Sessions = async_sessionmaker[AsyncSession]


# The model's quote must really appear in the posting, or the verification discards it.
LATAM_BODY = {"body": "[description]\nRemote within Latin America. Build user interfaces."}


class TitleLLM:
    """Answers "open to Latin America" for every posting, except the titles told to fail."""

    def __init__(self, failing_titles: tuple[str, ...] = ()) -> None:
        self.failing_titles = failing_titles

    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse:
        if any(title in messages[-1][1] for title in self.failing_titles):
            raise TimeoutError("provider timed out")
        facts = make_facts(restrictions=[make_restriction()])  # "Remote within Latin America"
        return BackendResponse(parsed=facts, usage=Usage(input_tokens=10, output_tokens=2))


@pytest.fixture(autouse=True)
def _model() -> Iterator[None]:
    """Every test here talks to a model that opens the job to Latin America."""
    with use_backend(TitleLLM()):
        yield


async def _claim_and_screen(
    sessions: Sessions, user_id: UUID, run_id: UUID, at: datetime = NOW
) -> tuple[list[UUID], ScreenStats]:
    async with sessions() as session:
        claimed = await claim_jobs(session, run_id, user_id, 10, at, STALE_SECONDS)
        profile = await session.get_one(Profile, user_id)
        await session.commit()
    constraints = Constraints.model_validate(profile.constraints)
    return claimed, await screen_jobs(sessions, run_id, claimed, constraints, 2, at)


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

    _, stats = await _claim_and_screen(committed_sessions, user_id, run_id)

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


async def test_a_failing_job_goes_back_to_pending_once_and_then_ends_failed(
    committed_sessions: Sessions,
):
    user_id, run_id = await queue_run(committed_sessions, 3, lambda n: LATAM_BODY)

    with use_backend(TitleLLM(failing_titles=("Role 1",))):
        _, first = await _claim_and_screen(committed_sessions, user_id, run_id)
        after_first = await _rows(committed_sessions, run_id)
        _, second = await _claim_and_screen(committed_sessions, user_id, run_id)
        after_second = await _rows(committed_sessions, run_id)

    assert (first.screened, first.errors) == (2, 1)  # the others were not affected
    assert after_first["Role 1"].status == "pending"  # one more chance
    assert after_first["Role 1"].last_error == "TimeoutError"
    assert (second.screened, second.errors) == (0, 1)  # only the retry was claimed
    assert (after_second["Role 1"].status, after_second["Role 1"].attempts) == ("failed", 2)
    assert after_second["Role 0"].status == after_second["Role 2"].status == "done"


async def test_a_finished_job_is_never_claimed_or_screened_again(committed_sessions: Sessions):
    user_id, run_id = await queue_run(committed_sessions, 2, lambda n: LATAM_BODY)
    await _claim_and_screen(committed_sessions, user_id, run_id)

    claimed, stats = await _claim_and_screen(committed_sessions, user_id, run_id)

    assert claimed == [] and stats == ScreenStats()
