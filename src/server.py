"""Build the MCP server: its startup and shutdown, its error handling and its tools."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import Settings
from src.core.http import make_http_client
from src.db.session import make_engine, make_session_factory
from src.routers.context import AppState
from src.routers.tools import register_mcp_tools
from src.sources.base import JobSource
from src.sources.registry import build_sources


def create_mcp_server(
    settings: Settings,
    *,
    engine: AsyncEngine | None = None,
    sources: list[JobSource] | None = None,
) -> FastMCP:
    """`engine` and `sources` are for tests, which bring a test database and fake sources.

    Left out, the server creates its own pool and HTTP client at startup and closes them at
    shutdown: both live as long as the process, never per request.
    """

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, AppState]]:
        own_engine = engine or make_engine(settings.database_url)
        if sources is None:
            http_client = make_http_client()
            active_sources = build_sources(settings, http_client)
        else:
            http_client, active_sources = None, sources
        state = AppState(make_session_factory(own_engine), settings, active_sources)
        try:
            yield {"app": state}
        finally:
            if http_client is not None:
                await http_client.aclose()
            if engine is None:  # a pool we were handed belongs to whoever created it
                await own_engine.dispose()

    mcp = FastMCP(
        "laburo-match",
        lifespan=lifespan,
        mask_error_details=True,
        strict_input_validation=True,
    )
    register_mcp_tools(mcp)
    return mcp
