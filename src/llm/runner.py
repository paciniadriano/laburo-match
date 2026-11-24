"""`llm.run()`: the only way the rest of the code calls a model."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from pydantic import BaseModel

from src.config.settings import get_settings
from src.core.errors import LLMOutputError
from src.llm.backend import LLMBackend, Usage
from src.llm.messages import build_messages
from src.llm.tasks import get_task
from src.llm.versioning import resolve_model, version_hash

# The backend is a client object (like a connection pool), not request state.
_backend: LLMBackend | None = None


def get_backend() -> LLMBackend:
    """The installed backend, or the real one built from settings on first use."""
    global _backend
    if _backend is None:
        from src.llm.openai_backend import OpenAIBackend  # heavy import, only when really needed

        _backend = OpenAIBackend(get_settings())
    return _backend


@contextmanager
def use_backend(backend: LLMBackend | None) -> Iterator[None]:
    """Install a backend for the duration of the block (tests install a FakeLLM)."""
    global _backend
    previous, _backend = _backend, backend
    try:
        yield
    finally:
        _backend = previous


@dataclass(frozen=True)
class LLMResult:
    output: BaseModel  # an instance of the task's `output_schema`
    usage: Usage  # summed over every attempt, because a retry costs tokens too
    attempts: int
    model: str
    version_hash: str  # cache key part: changes with prompt, examples, schema, model, params


async def run(task_name: str, variable_input: str) -> LLMResult:
    """Run one registered task on one piece of (untrusted) input.

    If the model's output does not validate, it gets exactly one more try, shown what was wrong.
    """
    task = get_task(task_name)
    settings = get_settings()
    model = resolve_model(task, settings)
    backend = get_backend()
    messages = build_messages(task, variable_input)

    usage = Usage()
    error = ""
    for attempt in (1, 2):
        response = await backend.complete(task=task, model=model, messages=messages)
        usage += response.usage
        if response.parsed is not None:
            return LLMResult(
                output=response.parsed,
                usage=usage,
                attempts=attempt,
                model=model,
                version_hash=version_hash(task, settings),
            )
        error = response.error
        messages = [
            *messages,
            (
                "user",
                f"Your previous answer was not valid: {error}\n"
                "Answer again, following the schema exactly.",
            ),
        ]
    raise LLMOutputError(task_name)
