"""The terminal client against the real server in memory: it lists the tools and runs one
scripted turn (search, screen until done, answer) on the test database."""

import json
from typing import Any

from fastmcp import Client
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from client.agent import run_turn
from client.display import show_tool_result
from client.tools import to_model_tools
from src.config.settings import Settings
from src.llm import use_backend
from src.prompts.workflow import server_instructions
from src.server import create_mcp_server
from tests.factories import make_source_job
from tests.fakes.fake_chat_model import ScriptedChatModel, call
from tests.fakes.fake_source import FakeSource
from tests.fakes.latam_llm import LATAM_BODY, LatamLLM
from tests.integration.test_mcp_tools import _seed_user

Sessions = async_sessionmaker[AsyncSession]
SETTINGS = Settings.from_env_file(None).model_copy(
    update={"screen_max_jobs_per_call": 2, "llm_concurrency": 2}
)


def _last_tool_data(history: list[BaseMessage]) -> dict[str, Any]:
    last = history[-1]
    assert isinstance(last, ToolMessage)
    return json.loads(str(last.content))


def _policy(history: list[BaseMessage]) -> AIMessage:
    """What a sensible model does: search, screen until done, then sum up."""
    last = history[-1]
    if not isinstance(last, ToolMessage):
        return call("search_jobs", "c1")
    data = _last_tool_data(history)
    if last.name == "search_jobs":
        return call("screen_batch", "c2", run_id=data["run_id"])
    if data["status"] == "partial":  # this user wants every job checked
        return call("screen_batch", "c3", run_id=_run_id(history))
    return AIMessage(content="Found 3 jobs you can look at.")


def _run_id(history: list[BaseMessage]) -> str:
    for message in history:
        if isinstance(message, ToolMessage) and message.name == "search_jobs":
            return json.loads(str(message.content))["run_id"]
    raise AssertionError("no search in the history")


async def test_the_client_lists_tools_and_runs_one_scripted_turn(
    engine: AsyncEngine, committed_sessions: Sessions
):
    await _seed_user(committed_sessions)
    jobs = [make_source_job(f"job-{n}", title=f"Role {n}", **LATAM_BODY) for n in range(3)]
    server = create_mcp_server(SETTINGS, engine=engine, sources=[FakeSource(jobs)])
    printed: list[str] = []
    model = ScriptedChatModel(_policy)
    history: list[BaseMessage] = [SystemMessage("rules")]

    with use_backend(LatamLLM()):
        async with Client(server) as mcp:
            tools = to_model_tools(await mcp.list_tools())
            assert {t["function"]["name"] for t in tools} == {"search_jobs", "screen_batch"}
            assert mcp.initialize_result is not None
            assert mcp.initialize_result.instructions == server_instructions()

            answer = await run_turn(
                model,
                mcp,
                history,
                "find me jobs",
                lambda name, result: show_tool_result(name, result, printed.append),
            )

    assert answer == "Found 3 jobs you can look at."
    assert model.calls == 4  # search, screen (in progress), screen (done), answer
    shortlist = printed[-1]
    assert shortlist.startswith("Shortlist: 3 eligible")
    assert shortlist.count("Apply (") == 3  # every card carries its apply link
    assert any("not checked yet" in line for line in printed)  # a partial list came first
