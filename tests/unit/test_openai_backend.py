from types import SimpleNamespace

from pydantic import SecretStr

from src.config.settings import Settings
from src.llm.openai_backend import OpenAIBackend, response_from_langchain
from src.llm.tasks import JOB_EXTRACTION
from tests.factories import make_facts

SETTINGS = Settings.from_env_file(None).model_copy(update={"openai_api_key": SecretStr("sk-test")})


def _raw(**usage: object) -> SimpleNamespace:
    return SimpleNamespace(usage_metadata=usage)


def test_tokens_and_cached_tokens_are_read_from_the_usage_metadata():
    raw = _raw(input_tokens=3269, output_tokens=257, input_token_details={"cache_read": 3254})

    response = response_from_langchain({"raw": raw, "parsed": make_facts(), "parsing_error": None})

    assert response.parsed is not None
    assert (response.usage.input_tokens, response.usage.output_tokens) == (3269, 257)
    assert response.usage.cached_tokens == 3254


def test_missing_usage_counts_as_zero():
    response = response_from_langchain(
        {"raw": _raw(), "parsed": make_facts(), "parsing_error": None}
    )

    assert (response.usage.input_tokens, response.usage.cached_tokens) == (0, 0)


def test_a_parsing_error_becomes_an_invalid_response_with_its_message():
    response = response_from_langchain(
        {"raw": _raw(input_tokens=10), "parsed": None, "parsing_error": ValueError("bad field")}
    )

    assert response.parsed is None
    assert "bad field" in response.error
    assert response.usage.input_tokens == 10  # an invalid answer still cost tokens


def test_the_client_uses_the_responses_api_with_the_task_settings():
    client = OpenAIBackend(SETTINGS).client_for(JOB_EXTRACTION, "gpt-6-luna")

    assert client.model_name == "gpt-6-luna"
    assert client.use_responses_api is True
    assert client.reasoning == {"effort": "low"}
    assert client.model_kwargs == {"prompt_cache_key": "job_extraction"}
    assert client.max_retries == 2


def test_the_same_client_is_reused_and_a_different_model_gets_its_own():
    backend = OpenAIBackend(SETTINGS)

    first = backend.client_for(JOB_EXTRACTION, "gpt-6-luna")

    assert backend.client_for(JOB_EXTRACTION, "gpt-6-luna") is first
    assert backend.client_for(JOB_EXTRACTION, "gpt-6-sol") is not first
