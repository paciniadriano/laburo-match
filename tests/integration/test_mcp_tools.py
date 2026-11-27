"""The tools called the way a host calls them: through an MCP client, against a real database."""

import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.app.profile.seed import seed_sample_profile
from src.config.settings import Settings
from src.llm import use_backend
from src.server import create_mcp_server
from tests.conftest import SAMPLE_EVIDENCE
from tests.factories import make_source_job
from tests.fakes.fake_source import ExplodingSource, FakeSource
from tests.fakes.latam_llm import LATAM_BODY, LatamLLM

Sessions = async_sessionmaker[AsyncSession]
SETTINGS = Settings.from_env_file(None).model_copy(
    update={"screen_max_jobs_per_call": 2, "llm_concurrency": 2}
)


async def _seed_user(sessions: Sessions) -> None:
    async with sessions() as session:
        sample = json.loads(SAMPLE_EVIDENCE.read_text())
        await seed_sample_profile(session, sample, max_job_age_days=30)
        await session.commit()


def _error_text(result: CallToolResult) -> str:
    assert result.is_error
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _client(engine: AsyncEngine, *sources: Any) -> Client:
    return Client(create_mcp_server(SETTINGS, engine=engine, sources=list(sources)))


async def test_search_then_screen_in_rounds_shows_results_every_round(
    engine: AsyncEngine, committed_sessions: Sessions
):
    await _seed_user(committed_sessions)
    jobs = [make_source_job(f"job-{n}", title=f"Role {n}", **LATAM_BODY) for n in range(5)]
    steps: list[dict[str, Any]] = []

    with use_backend(LatamLLM()):
        async with _client(engine, FakeSource(jobs)) as client:
            search = (await client.call_tool("search_jobs", {})).structured_content
            assert search is not None and search["to_screen"] == 5
            while not steps or steps[-1]["status"] != "done":
                step = await client.call_tool("screen_batch", {"run_id": search["run_id"]})
                assert step.structured_content is not None
                steps.append(step.structured_content)

    assert [s["status"] for s in steps] == ["partial", "partial", "done"]
    assert [s["remaining"] for s in steps] == [3, 1, 0]
    final = steps[-1]
    assert final["processed"] == 5 and len(final["shortlist"]) == 5
    assert "not legal advice" in final["disclaimer"]
    assert [len(s["shortlist"]) for s in steps] == [2, 4, 5]  # the best so far, every round


async def test_a_source_that_is_down_becomes_a_warning_and_the_search_goes_on(
    engine: AsyncEngine, committed_sessions: Sessions
):
    await _seed_user(committed_sessions)
    working = FakeSource([make_source_job("a", **LATAM_BODY)])

    async with _client(engine, ExplodingSource(), working) as client:
        search = (await client.call_tool("search_jobs", {})).structured_content

    assert search is not None
    assert search["to_screen"] == 1
    assert any("explosive" in warning for warning in search["warnings"])


async def test_a_domain_error_reaches_the_host_with_its_stable_code(
    engine: AsyncEngine, committed_sessions: Sessions
):
    await _seed_user(committed_sessions)

    async with _client(engine) as client:
        result = await client.call_tool("screen_batch", {"run_id": "3"}, raise_on_error=False)

    assert result.is_error
    text = _error_text(result)
    assert text.startswith("[RUN_NOT_FOUND]")
    assert "job_id" not in text and "Traceback" not in text


async def test_a_caller_with_no_profile_is_told_to_set_one_up(
    engine: AsyncEngine, committed_sessions: Sessions
):
    async with _client(engine) as client:  # nobody seeded: the database is empty
        result = await client.call_tool("search_jobs", {}, raise_on_error=False)

    assert result.is_error
    assert _error_text(result).startswith("[PROFILE_REQUIRED]")


async def test_an_unexpected_error_never_leaks_its_details(
    engine: AsyncEngine, committed_sessions: Sessions, monkeypatch: pytest.MonkeyPatch
):
    await _seed_user(committed_sessions)

    async def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("password=hunter2 in /srv/secret/config")

    monkeypatch.setattr("src.routers.tools.screen_batch_tool", explode)
    async with _client(engine) as client:
        result = await client.call_tool("screen_batch", {"run_id": "x"}, raise_on_error=False)

    assert result.is_error
    text = _error_text(result)
    assert "hunter2" not in text and "secret" not in text


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("search_jobs", {"max_new": "30"}),  # a string is not silently turned into a number
        ("search_jobs", {"max_new": 30, "user_id": "someone-else"}),  # unknown argument
        ("screen_batch", {}),  # missing required argument
    ],
)
async def test_invalid_arguments_are_rejected_not_coerced(
    engine: AsyncEngine, committed_sessions: Sessions, tool: str, arguments: dict[str, Any]
):
    await _seed_user(committed_sessions)

    async with _client(engine) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)

    assert result.is_error
