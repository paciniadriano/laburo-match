"""Call the running server like a host would, with a client-side timeout. Usage: probe.py TOOL SECONDS [CLIENT_TIMEOUT]"""
import asyncio
import sys
import time

from fastmcp import Client

tool, seconds = sys.argv[1], int(sys.argv[2])
timeout = float(sys.argv[3]) if len(sys.argv) > 3 else None
events = []


async def on_progress(progress, total, message):
    events.append((round(time.monotonic() - t0, 1), message))


async def main():
    async with Client("http://127.0.0.1:8000/mcp", timeout=timeout) as c:
        tools = [t.name for t in await c.list_tools()]
        print("tools:", tools)
        res = await c.call_tool(tool, {"seconds": seconds}, progress_handler=on_progress)
        print("result:", res.content[0].text)


t0 = time.monotonic()
try:
    asyncio.run(main())
except Exception as exc:
    print(f"CLIENT GAVE UP after {time.monotonic() - t0:.1f}s: {type(exc).__name__}: {str(exc)[:90]}")
print(f"progress events received: {len(events)}", events[:3], "...")
