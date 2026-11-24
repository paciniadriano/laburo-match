"""Spike 1.3: tools that take a controlled time, to measure each host's timeout."""
import asyncio
import time

from fastmcp import Context, FastMCP

mcp = FastMCP("spike-timeouts")


@mcp.tool(annotations={"readOnlyHint": True})
async def sleep_plain(seconds: int) -> str:
    """Wait `seconds` seconds and answer once at the end. No progress notifications."""
    start = time.monotonic()
    await asyncio.sleep(seconds)
    return f"plain: finished after {time.monotonic() - start:.1f}s"


@mcp.tool(annotations={"readOnlyHint": True})
async def sleep_progress(seconds: int, ctx: Context) -> str:
    """Wait `seconds` seconds, sending one progress notification per second."""
    start = time.monotonic()
    for i in range(seconds):
        await asyncio.sleep(1)
        await ctx.report_progress(progress=i + 1, total=seconds, message=f"{i + 1}/{seconds}s")
    return f"progress: finished after {time.monotonic() - start:.1f}s"


@mcp.tool(annotations={"readOnlyHint": True})
async def draft_loop(rounds: int = 4) -> str:
    """Draft-like loop: writer, reviewer, editor, reviewer. Returns per-call timings."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-6-luna", use_responses_api=True, reasoning={"effort": "low"})
    steps = ["Write a 200-word cover letter for a backend engineer applying to a fintech.",
             "Review the letter for clichés and unverifiable claims. List the problems.",
             "Rewrite the letter fixing those problems, about 200 words.",
             "Review again and answer APPROVED or list remaining problems."]
    text, times = "", []
    for i in range(rounds):
        t = time.monotonic()
        r = await llm.ainvoke(f"{steps[i % len(steps)]}\n\nPrevious text:\n{text[:1500]}")
        text = str(r.content)
        times.append(round(time.monotonic() - t, 1))
    return f"loop timings (s): {times} total={round(sum(times), 1)}"


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")
