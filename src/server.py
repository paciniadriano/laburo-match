"""Build the MCP server: its startup and shutdown, its error handling and its tools."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from fastmcp import FastMCP
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import Settings
from src.core.http import make_http_client
from src.db.session import make_engine, make_session_factory
from src.prompts.workflow import server_instructions
from src.routers.context import AppState
from src.routers.health import register_health_routes
from src.routers.tools import register_mcp_tools
from src.sources.base import JobSource
from src.sources.registry import build_sources

logger = logging.getLogger(__name__)


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

    running: list[AppState] = []  # filled while the lifespan runs, so /ready can reach the pool

    async def database_is_reachable() -> bool:
        if not running:
            return False
        try:
            async with running[0].sessions() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            logger.warning("readiness check failed", exc_info=False)
            return False
        return True

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, AppState]]:
        own_engine = engine or make_engine(settings.database_url)
        if sources is None:
            http_client = make_http_client()
            active_sources = build_sources(settings, http_client)
        else:
            http_client, active_sources = None, sources
        state = AppState(make_session_factory(own_engine), settings, active_sources)
        running.append(state)
        try:
            yield {"app": state}
        finally:
            running.clear()
            if http_client is not None:
                await http_client.aclose()
            if engine is None:  # a pool we were handed belongs to whoever created it
                await own_engine.dispose()

    mcp = FastMCP(
        "laburo-match",
        instructions=server_instructions(),
        lifespan=lifespan,
        mask_error_details=True,
        strict_input_validation=True,
    )
    register_mcp_tools(mcp)
    register_health_routes(mcp, database_is_reachable)
    return mcp


def http_options(settings: Settings) -> dict[str, Any]:
    """Options for `run()`/`http_app()` that depend on the mode.

    The Host/Origin guard is always on: a browser page must not reach a server bound to
    loopback through DNS rebinding. Allowed hosts are the local ones plus the public host of
    `PUBLIC_BASE_URL`. Production is stateless: no session lives in memory, so any replica can
    answer any request.
    """
    allowed = {f"localhost:{settings.server_port}", f"127.0.0.1:{settings.server_port}"}
    public = urlsplit(settings.public_base_url)
    if public.netloc:
        allowed.add(public.netloc)
    return {
        "host_origin_protection": True,
        "allowed_hosts": sorted(allowed),
        "stateless_http": settings.app_env == "production",
    }
