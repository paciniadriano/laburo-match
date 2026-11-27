"""The one place that builds a `ChatOpenAI` client, for server tasks and for the terminal client.

Spike 1.4 measured what the provider accepts: no `temperature`, effort `none` or `low`.
"""

from typing import Any

from langchain_openai import ChatOpenAI

from src.config.constants import LLM_MAX_RETRIES, LLM_REQUEST_TIMEOUT_SECONDS
from src.config.settings import Settings


def build_chat_model(
    settings: Settings,
    *,
    model: str,
    reasoning_effort: str,
    cache_key: str,
    max_output_tokens: int | None = None,
) -> ChatOpenAI:
    """A client on the Responses API.

    `cache_key` is the same for every call of a task, so requests that share a prefix reach the
    same cache. It is only a routing hint, never user data.
    """
    extra: dict[str, Any] = (
        {"max_tokens": max_output_tokens} if max_output_tokens is not None else {}
    )
    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        use_responses_api=True,
        reasoning={"effort": reasoning_effort},
        timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
        model_kwargs={"prompt_cache_key": cache_key},
        **extra,
    )
