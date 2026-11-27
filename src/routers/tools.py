"""The MCP contract of the tools: names, descriptions, parameters and hints. No logic here.

Descriptions are written for the host's model, so they say *when* to call the tool and *what
to do next*. Annotations are hints to the host, never security: every guard is in server code.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from src.models.listing import ListJobsResult, ListStatus
from src.models.screening import ScreenBatchResult
from src.models.search import SearchSummary
from src.routers.context import app_state, current_user_id, user_session
from src.routers.error_mapping import maps_domain_errors
from src.tools.list_jobs import list_jobs_tool
from src.tools.screen_batch import screen_batch_tool
from src.tools.search_jobs import search_jobs_tool


def register_mcp_tools(mcp: FastMCP) -> None:
    def tool(**options: Any) -> Callable[[Callable[..., Awaitable[Any]]], Any]:
        """`mcp.tool` plus the error translation, so no tool can be registered without it."""

        def register(function: Callable[..., Awaitable[Any]]) -> Any:
            return mcp.tool(**options)(maps_domain_errors(function))

        return register

    @tool(
        name="search_jobs",
        annotations=ToolAnnotations(
            readOnlyHint=False,  # creates a search run
            destructiveHint=False,
            idempotentHint=False,  # a second call may find new jobs and makes a new run
            openWorldHint=True,  # asks external job sources
        ),
    )
    async def search_jobs(ctx: Context, max_new: int = 300) -> SearchSummary:
        """Find new jobs for the user's profile and queue them for analysis.

        Fast: it only collects and filters postings; it does not say whether the user can
        apply. Requires a complete profile. It queues every new job that passes the filters;
        leave `max_new` at its default unless the user asks for fewer. Afterwards call
        screen_batch with the returned run_id.
        """
        state = app_state(ctx)
        async with user_session(state) as (session, user_id):
            return await search_jobs_tool(session, state.sources, state.settings, user_id, max_new)

    @tool(
        name="screen_batch",
        annotations=ToolAnnotations(
            readOnlyHint=False,  # records verdicts
            destructiveHint=False,
            idempotentHint=True,  # repeating a call never redoes finished work
            openWorldHint=False,
        ),
    )
    async def screen_batch(ctx: Context, run_id: str) -> ScreenBatchResult:
        """Analyze the next jobs of a search run: can the user apply from where they live?

        Takes the run_id returned by search_jobs. Each call works for about 20 seconds, most
        relevant jobs first, and returns the best ones judged so far: show them right away. If
        `remaining` is above 0, offer to check more and call again with the same run_id only
        when the user wants it. Eligibility is an estimate from the posting text, never legal
        advice.
        """
        state = app_state(ctx)
        user_id = await current_user_id(state)
        return await screen_batch_tool(state.sessions, state.settings, user_id, run_id)

    @tool(
        name="list_jobs",
        annotations=ToolAnnotations(
            readOnlyHint=True,  # reads verdicts, never changes them
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_jobs(
        ctx: Context, status: ListStatus = "all", limit: int = 20, offset: int = 0
    ) -> ListJobsResult:
        """List every job already judged for the user, beyond the 10 cards of a shortlist.

        `status="all"` lists the jobs the user can look at (eligible first); `"filtered"` lists
        what was left out automatically, each with the reason, so the user can check it. Pages
        of `limit` jobs (at most 50): pass `offset` from the hint for the next one. Read-only.
        """
        state = app_state(ctx)
        async with user_session(state) as (session, user_id):
            return await list_jobs_tool(session, user_id, status, limit, offset)
