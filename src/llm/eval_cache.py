"""A disk cache of model answers, for the eval runner only (the server never uses it).

An eval run repeats the same calls many times while rules and metrics are being tuned; the
answer to an identical request does not change, so it is paid for once. The key covers
everything that shapes the answer: task, model, parameters, output schema and the exact
messages. `--no-cache` skips it for experiments on the prompt itself.
"""

import hashlib
import json
from pathlib import Path

from src.llm.backend import BackendResponse, LLMBackend, Usage
from src.llm.messages import Message
from src.llm.tasks import LLMTask


def cache_key(task: LLMTask, model: str, messages: list[Message]) -> str:
    payload = {
        "task": task.name,
        "model": model,
        "reasoning_effort": task.reasoning_effort,
        "max_output_tokens": task.max_output_tokens,
        "schema": task.output_schema.model_json_schema(),
        "messages": messages,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class CachingBackend:
    def __init__(self, inner: LLMBackend, directory: Path) -> None:
        self._inner = inner
        self._directory = directory
        self.hits = 0
        self.misses = 0

    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse:
        path = self._directory / f"{cache_key(task, model, messages)}.json"
        if path.exists():
            self.hits += 1
            parsed = task.output_schema.model_validate_json(path.read_text())
            return BackendResponse(parsed, Usage())  # a hit costs nothing
        self.misses += 1
        response = await self._inner.complete(task=task, model=model, messages=messages)
        if response.parsed is not None:  # an invalid answer is never worth replaying
            self._directory.mkdir(parents=True, exist_ok=True)
            path.write_text(response.parsed.model_dump_json())
        return response
