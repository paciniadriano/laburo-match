"""`make client`: a terminal chat over the MCP server (`python -m client.main [--url URL]`)."""

import argparse
import asyncio
import time

from fastmcp import Client
from langchain_core.messages import BaseMessage, SystemMessage

from client.agent import ChatModel, run_turn
from client.display import show_tool_result
from client.tools import to_model_tools
from src.config.settings import Settings, get_settings
from src.llm.factory import build_chat_model

CLIENT_RULES = (
    "You are the terminal assistant of laburo-match. After every screen_batch and list_jobs "
    "the program prints the results itself, with links and quotes: do not repeat them. Reply "
    "with two or three sentences that sum up what was found and, if jobs remain unchecked, "
    "offer to check more. Answer in the user's language."
)


def build_model(settings: Settings, tools: list[dict]) -> ChatModel:
    chat = build_chat_model(
        settings,
        model=settings.llm_client_model or settings.llm_base_model,
        reasoning_effort="low",
        cache_key="client",
    )
    return chat.bind_tools(tools)  # pyright: ignore[reportReturnType]


async def chat_loop(model: ChatModel, mcp: Client, system_prompt: str) -> None:
    history: list[BaseMessage] = [SystemMessage(system_prompt)]
    print("laburo-match. Type /quit to leave.")
    while True:
        try:
            line = (await asyncio.to_thread(input, "you> ")).strip()
        except EOFError:
            break
        if line in {"/quit", "/exit"}:
            break
        if not line:
            continue
        started = time.monotonic()
        try:
            answer = await run_turn(model, mcp, history, line, show_tool_result)
            # The wait the user felt, end to end: the number the ~30 s target is about.
            print(f"{answer}\n({time.monotonic() - started:.0f} s)")
        except Exception as error:  # keep the chat alive; never print a stack trace
            print(f"Something went wrong: {type(error).__name__}: {error}")


async def main(url: str) -> None:
    settings = get_settings()
    if not settings.openai_api_key.get_secret_value():
        raise SystemExit(
            "OPENAI_API_KEY is empty: set it in the .env that ENV_FILE_PATH points to."
        )
    async with Client(url) as mcp:
        tools = to_model_tools(await mcp.list_tools())
        initialized = mcp.initialize_result
        instructions = (initialized.instructions if initialized else "") or ""
        await chat_loop(build_model(settings, tools), mcp, f"{instructions}\n\n{CLIENT_RULES}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000/mcp")
    asyncio.run(main(parser.parse_args().url))
