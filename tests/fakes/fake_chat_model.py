"""A scripted stand-in for the client's chat model. Strict like `FakeLLM`: a call beyond the
script is an error, so a loop that never ends fails the test instead of spinning."""

from collections.abc import Callable

from langchain_core.messages import AIMessage, BaseMessage

Policy = Callable[[list[BaseMessage]], AIMessage]


class ScriptedChatModel:
    """Decides each reply from the history so far (ids such as `run_id` are not known upfront)."""

    def __init__(self, policy: Policy, max_calls: int = 20) -> None:
        self._policy = policy
        self._max_calls = max_calls
        self.calls = 0

    async def ainvoke(self, messages: list[BaseMessage]) -> AIMessage:
        self.calls += 1
        if self.calls > self._max_calls:
            raise AssertionError("the scripted model was called more than the test expected")
        return self._policy(messages)


def call(name: str, call_id: str, **args: object) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])
