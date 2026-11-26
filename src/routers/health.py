"""Operational routes for the platform (Docker, Azure), not for MCP hosts.

`/health` says the process is alive; `/ready` says it can serve. They are separate because a
platform restarts a container that fails liveness, while a failed readiness only stops traffic:
a database outage must not put the server in a restart loop.
"""

from collections.abc import Awaitable, Callable

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

ReadyProbe = Callable[[], Awaitable[bool]]


def register_health_routes(mcp: FastMCP, is_ready: ReadyProbe) -> None:
    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @mcp.custom_route("/ready", methods=["GET"])
    async def ready(_: Request) -> JSONResponse:
        if await is_ready():
            return JSONResponse({"status": "ready"})
        return JSONResponse({"status": "not_ready"}, status_code=503)
