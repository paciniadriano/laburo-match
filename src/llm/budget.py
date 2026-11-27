"""A backend wrapper that counts what every real call costs and stops at a budget."""

from src.core.usage import BudgetGuard
from src.llm.backend import BackendResponse, LLMBackend
from src.llm.messages import Message
from src.llm.tasks import LLMTask


class BudgetedBackend:
    def __init__(self, inner: LLMBackend, guard: BudgetGuard) -> None:
        self._inner = inner
        self._guard = guard

    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse:
        self._guard.ensure_room()
        response = await self._inner.complete(task=task, model=model, messages=messages)
        self._guard.charge(model, response.usage)  # an invalid answer cost tokens too
        return response
