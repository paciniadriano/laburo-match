"""The ReAct loop, with a fake model and a fake tool caller (no server, no database)."""

from typing import Any

from fastmcp.client.client import CallToolResult
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from mcp.types import TextContent

from client.agent import STEP_LIMIT_MESSAGE, run_turn
from tests.fakes.fake_chat_model import ScriptedChatModel, call


class FakeTools:
    def __init__(self, result: CallToolResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None, *, raise_on_error: bool = True
    ) -> CallToolResult:
        assert raise_on_error is False  # an error must reach the model, not break the loop
        self.calls.append((name, arguments or {}))
        return self.result


def _result(data: dict[str, Any] | None, *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[], structured_content=data, meta=None, data=None, is_error=is_error
    )


async def test_the_loop_calls_a_tool_then_answers_with_what_it_read():
    def policy(history: list[BaseMessage]) -> AIMessage:
        last = history[-1]
        if isinstance(last, ToolMessage):
            return AIMessage(content=f"saw {last.content}")
        return call("search_jobs", "c1", max_new=5)

    tools = FakeTools(_result({"to_screen": 3}))
    history: list[BaseMessage] = [SystemMessage("rules")]

    answer = await run_turn(ScriptedChatModel(policy), tools, history, "find jobs")

    assert answer == 'saw {"to_screen": 3}'
    assert tools.calls == [("search_jobs", {"max_new": 5})]
    assert [type(m).__name__ for m in history] == [
        "SystemMessage", "HumanMessage", "AIMessage", "ToolMessage", "AIMessage",
    ]  # fmt: skip


async def test_a_tool_error_goes_back_to_the_model_as_text():
    seen: list[str] = []

    def policy(history: list[BaseMessage]) -> AIMessage:
        last = history[-1]
        if isinstance(last, ToolMessage):
            seen.append(str(last.content))
            return AIMessage(content="ok")
        return call("screen_batch", "c1", run_id="x")

    error = CallToolResult(
        content=[TextContent(type="text", text="[RUN_NOT_FOUND] no such run")],
        structured_content=None,
        meta=None,
        data=None,
        is_error=True,
    )
    await run_turn(ScriptedChatModel(policy), FakeTools(error), [], "go")

    assert seen == ["[RUN_NOT_FOUND] no such run"]


async def test_a_model_that_never_stops_calling_tools_is_cut_off():
    model = ScriptedChatModel(lambda history: call("search_jobs", "c"))

    answer = await run_turn(model, FakeTools(_result({"to_screen": 0})), [], "go", max_steps=3)

    assert answer == STEP_LIMIT_MESSAGE
    assert model.calls == 3
