"""The ReAct loop: the model asks for a tool, we call it, the model reads the result, repeat.

Written by hand instead of with LangGraph: LangGraph is only for the server's draft workflow,
and this loop is a dozen lines.
"""

import json
from collections.abc import Callable
from typing import Any, Protocol

from fastmcp.client.client import CallToolResult
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from mcp.types import TextContent

# One user request needs about 4 calls (search, screen, screen, answer); this is the safety net
# against a model that keeps calling tools forever.
MAX_STEPS = 12

STEP_LIMIT_MESSAGE = "I stopped after too many steps without finishing. Ask me to continue."

ToolListener = Callable[[str, CallToolResult], None]


class ChatModel(Protocol):
    """What the loop needs from a model: `ChatOpenAI(...).bind_tools(...)` or a test script."""

    async def ainvoke(self, messages: list[BaseMessage]) -> AIMessage: ...


class ToolCaller(Protocol):
    """What the loop needs from the MCP client."""

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None, *, raise_on_error: bool = True
    ) -> Any: ...


def result_text(result: CallToolResult) -> str:
    """What the model reads back: the structured result when there is one, else the text.

    A tool error is returned as text too, so the model can react to it instead of crashing the loop.
    """
    if result.structured_content is not None:
        return json.dumps(result.structured_content)
    return "\n".join(b.text for b in result.content if isinstance(b, TextContent))


async def run_turn(
    model: ChatModel,
    mcp: ToolCaller,
    history: list[BaseMessage],
    user_text: str,
    on_tool_result: ToolListener | None = None,
    max_steps: int = MAX_STEPS,
) -> str:
    """Answer one user message. `history` keeps the conversation across turns."""
    history.append(HumanMessage(user_text))
    for _ in range(max_steps):
        reply = await model.ainvoke(history)
        history.append(reply)
        if not reply.tool_calls:
            return reply.text
        for call in reply.tool_calls:
            result = await mcp.call_tool(call["name"], call["args"], raise_on_error=False)
            if on_tool_result:
                on_tool_result(call["name"], result)
            history.append(
                ToolMessage(content=result_text(result), tool_call_id=call["id"], name=call["name"])
            )
    return STEP_LIMIT_MESSAGE
