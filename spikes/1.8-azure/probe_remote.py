"""Spike 1.8 probe: call the hello-world server and report timings, session info and progress events.

    uv run python spikes/1.8-azure/probe_remote.py http://127.0.0.1:8001/mcp
    uv run python spikes/1.8-azure/probe_remote.py https://<app>.<region>.azurecontainerapps.io/mcp --first-call
"""

import asyncio
import sys
import time

from fastmcp import Client


async def timed(label: str, coro):
    start = time.monotonic()
    result = await coro
    print(f"  {label:<34} {time.monotonic() - start:6.2f}s")
    return result


def text(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


async def main(url: str, first_call_only: bool) -> None:
    print(f"target: {url}")
    async with Client(url, timeout=60) as client:
        # `async with` already performs the initialize handshake: the cold start, if any, is paid here.
        if first_call_only:
            return
        tools = await timed("list_tools", client.list_tools())
        print("  tools:", [t.name for t in tools])
        print("  ->", text(await timed("whoami", client.call_tool("whoami", {}))))
        for i in (1, 2):
            print(f"  -> #{i}", text(await timed(f"session_info #{i}", client.call_tool("session_info", {}))))

        events: list[tuple[float, float | None, str | None]] = []

        async def on_progress(progress: float, total: float | None, message: str | None) -> None:
            events.append((progress, total, message))

        out = await timed("sleep_progress(5)", client.call_tool("sleep_progress", {"seconds": 5}, progress_handler=on_progress))
        print("  ->", text(out))
        print(f"  progress events received: {len(events)} {events[:2]}{' ...' if len(events) > 2 else ''}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], "--first-call" in sys.argv))
