"""The seam between `llm.run()` and a model provider."""

from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from src.llm.messages import Message
from src.llm.tasks import LLMTask


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0  # input tokens served from the provider's prompt cache

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cached_tokens + other.cached_tokens,
        )


@dataclass(frozen=True)
class BackendResponse:
    """`parsed` is the validated output, or None with `error` saying why it was not valid."""

    parsed: BaseModel | None
    usage: Usage = field(default_factory=Usage)
    error: str = ""


class LLMBackend(Protocol):
    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse: ...
