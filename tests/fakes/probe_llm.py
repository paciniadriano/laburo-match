"""A model that answers slowly and records how many calls were running at once."""

import asyncio

from src.llm.backend import BackendResponse, Usage
from src.llm.messages import Message
from src.llm.tasks import LLMTask
from tests.factories import make_facts


class ProbeLLM:
    """A model that answers slowly and records how many calls were running at once."""

    def __init__(self, fail_for: str = "") -> None:
        self.fail_for = fail_for
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls_started_while_first_waited = 0
        self.calls = 0

    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse:
        self.calls += 1
        self.in_flight += 1
        if self.calls == 1:
            await asyncio.sleep(0.05)  # long enough for a wrongly launched neighbour to start
            self.calls_started_while_first_waited = self.calls
        else:
            await asyncio.sleep(0.02)
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.in_flight -= 1
        if self.fail_for and self.fail_for in messages[-1][1]:
            raise TimeoutError("provider timed out")
        return BackendResponse(parsed=make_facts(), usage=Usage(input_tokens=10, output_tokens=2))
