"""Spike 1.8: hello-world MCP server for Azure Container Apps (stateless HTTP).

Questions this server answers once deployed:
- does a stateless server work behind the Container Apps HTTPS ingress, from Claude Code?
- do progress notifications arrive when stateless_http=True?
- what is ctx.session_id when there is no session state?
- how long does the first call take after scale to zero (cold start)?

Public endpoint without auth: it is ephemeral and every tool is harmless and bounded.
"""

import asyncio
import os
import socket
import time

from fastmcp import Context, FastMCP

mcp = FastMCP("spike-azure")
STARTED = time.time()


@mcp.tool(annotations={"readOnlyHint": True})
async def whoami() -> str:
    """Where is this running? Container hostname, revision and seconds since the process started."""
    revision = os.environ.get("CONTAINER_APP_REVISION", "local")
    return f"host={socket.gethostname()} revision={revision} uptime={time.time() - STARTED:.1f}s"


@mcp.tool(annotations={"readOnlyHint": True})
async def session_info(ctx: Context) -> str:
    """Report what the server sees as session id and request id (stateless mode)."""

    def safe(name: str) -> str:
        try:
            return repr(getattr(ctx, name))
        except Exception as exc:  # the attribute itself may raise when there is no session
            return f"<{type(exc).__name__}: {exc}>"

    return f"session_id={safe('session_id')} request_id={safe('request_id')} host={socket.gethostname()}"


@mcp.tool(annotations={"readOnlyHint": True})
async def sleep_progress(seconds: int, ctx: Context) -> str:
    """Wait up to 30 seconds, sending one progress notification per second."""
    seconds = max(1, min(seconds, 30))  # public endpoint: cap the work a caller can ask for
    start = time.monotonic()
    for i in range(seconds):
        await asyncio.sleep(1)
        await ctx.report_progress(progress=i + 1, total=seconds, message=f"{i + 1}/{seconds}s")
    return f"progress: finished after {time.monotonic() - start:.1f}s on {socket.gethostname()}"


if __name__ == "__main__":
    # 0.0.0.0 inside the container; the platform ingress is what is exposed. stateless_http: no session kept in memory.
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), path="/mcp", stateless_http=True)
