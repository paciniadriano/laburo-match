"""A model for screening tests: every posting says "Remote within Latin America".

Unlike `FakeLLM` it needs no script, which suits tests where many jobs are screened and only
the outcome matters. Titles listed in `failing_titles` make the provider time out.
"""

import asyncio

from src.llm.backend import BackendResponse, Usage
from src.llm.messages import Message
from src.llm.tasks import LLMTask
from tests.factories import make_facts, make_restriction

# The model's quote must really appear in the posting, or the verification discards it.
LATAM_BODY = {"body": "[description]\nRemote within Latin America. Build user interfaces."}


class LatamLLM:
    def __init__(self, failing_titles: tuple[str, ...] = (), delay: float = 0) -> None:
        self.failing_titles = failing_titles
        self.delay = delay
        self.calls = 0
        self.started = asyncio.Event()  # set when the first call begins

    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse:
        self.calls += 1
        self.started.set()
        if self.delay:
            await asyncio.sleep(self.delay)
        if any(title in messages[-1][1] for title in self.failing_titles):
            raise TimeoutError("provider timed out")
        facts = make_facts(restrictions=[make_restriction()])
        return BackendResponse(parsed=facts, usage=Usage(input_tokens=10, output_tokens=2))
