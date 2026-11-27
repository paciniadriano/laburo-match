"""The real backend: `ChatOpenAI` on the Responses API with strict structured output.

The only module that talks to the provider. Spike 1.4 measured what it accepts: `temperature`
and reasoning effort `minimal` are rejected with a 400, `none` and `low` work.
"""

from typing import Any

from langchain_openai import ChatOpenAI

from src.config.settings import Settings
from src.llm.backend import BackendResponse, Usage
from src.llm.factory import build_chat_model
from src.llm.messages import Message
from src.llm.tasks import LLMTask


def response_from_langchain(result: dict[str, Any]) -> BackendResponse:
    """Translate LangChain's `{raw, parsed, parsing_error}` into a `BackendResponse`."""
    metadata = getattr(result.get("raw"), "usage_metadata", None) or {}
    usage = Usage(
        input_tokens=metadata.get("input_tokens", 0),
        output_tokens=metadata.get("output_tokens", 0),
        cached_tokens=(metadata.get("input_token_details") or {}).get("cache_read", 0),
    )
    parsed = result.get("parsed")
    if parsed is None:
        error = result.get("parsing_error")
        return BackendResponse(None, usage, str(error) if error else "the model returned no output")
    return BackendResponse(parsed, usage)


class OpenAIBackend:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._clients: dict[tuple[str, str, str, int | None], ChatOpenAI] = {}

    def client_for(self, task: LLMTask, model: str) -> ChatOpenAI:
        """One client per (model, task, effort, token cap), built lazily and reused."""
        key = (model, task.name, task.reasoning_effort, task.max_output_tokens)
        if key not in self._clients:
            self._clients[key] = build_chat_model(
                self._settings,
                model=model,
                reasoning_effort=task.reasoning_effort,
                cache_key=task.name,
                max_output_tokens=task.max_output_tokens,
            )
        return self._clients[key]

    async def complete(
        self, *, task: LLMTask, model: str, messages: list[Message]
    ) -> BackendResponse:
        chain = self.client_for(task, model).with_structured_output(
            task.output_schema, method="json_schema", strict=True, include_raw=True
        )
        result: dict[str, Any] = await chain.ainvoke(messages)  # pyright: ignore[reportAssignmentType]
        return response_from_langchain(result)
