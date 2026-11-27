"""A scripted stand-in for the model provider. Any call it was not told to expect fails loudly."""

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from src.llm.backend import BackendResponse, Usage
from src.llm.messages import Message
from src.llm.tasks import LLMTask


@dataclass(frozen=True)
class InvalidOutput:
    """Script this to simulate a model answer that does not validate."""

    error: str = "output does not match the schema"


# A response is a ready answer, an invalid answer, an exception to raise, or a function that
# builds the answer from the messages (needed when parallel calls arrive in any order).
Scripted = BaseModel | InvalidOutput | Exception | Callable[[list[Message]], BaseModel]


@dataclass(frozen=True)
class FakeCall:
    task: str
    model: str
    messages: list[Message]


class UnscriptedLLMCall(AssertionError):
    pass


DEFAULT_USAGE = Usage(input_tokens=100, output_tokens=20)


class FakeLLM:
    def __init__(self, usage: Usage = DEFAULT_USAGE) -> None:
        self._scripts: dict[str, deque[Scripted]] = defaultdict(deque)
        self._usage = usage
        self.calls: list[FakeCall] = []

    def script(self, task_name: str, *responses: Scripted) -> None:
        """Queue answers for a task; each call consumes the next one, in order."""
        self._scripts[task_name].extend(responses)

    def calls_for(self, task_name: str) -> list[FakeCall]:
        return [call for call in self.calls if call.task == task_name]

    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse:
        self.calls.append(FakeCall(task.name, model, messages))
        queue = self._scripts[task.name]
        if not queue:
            raise UnscriptedLLMCall(
                f"Unscripted LLM call for task {task.name!r} (call #{len(self.calls)})."
            )
        response = queue.popleft()
        if isinstance(response, Exception):
            raise response
        if isinstance(response, InvalidOutput):
            return BackendResponse(parsed=None, usage=self._usage, error=response.error)
        parsed = response(messages) if callable(response) else response
        if not isinstance(parsed, task.output_schema):
            raise AssertionError(
                f"Scripted answer for {task.name!r} is a {type(parsed).__name__}, "
                f"expected {task.output_schema.__name__}."
            )
        return BackendResponse(parsed=parsed, usage=self._usage)
