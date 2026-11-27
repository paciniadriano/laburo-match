import pytest

from src import llm
from src.core.errors import LLMOutputError
from src.models.job_facts import JobFacts
from tests.factories import make_facts
from tests.fakes.fake_llm import FakeLLM, InvalidOutput, UnscriptedLLMCall


async def test_run_returns_the_scripted_output_with_usage_and_version(fake_llm: FakeLLM):
    facts = make_facts(language="es")
    fake_llm.script("job_extraction", facts)

    result = await llm.run("job_extraction", "Desarrollador frontend, remoto")

    assert result.output == facts
    assert result.attempts == 1
    assert (result.usage.input_tokens, result.usage.output_tokens) == (100, 20)
    assert len(result.version_hash) == 64
    assert result.model  # the resolved model name is reported


async def test_an_unscripted_call_fails_loudly(fake_llm: FakeLLM):
    with pytest.raises(UnscriptedLLMCall, match="job_extraction"):
        await llm.run("job_extraction", "anything")


async def test_an_invalid_answer_is_retried_once_showing_the_error(fake_llm: FakeLLM):
    fake_llm.script("job_extraction", InvalidOutput("quotes must be a list"), make_facts())

    result = await llm.run("job_extraction", "a posting")

    assert result.attempts == 2
    assert result.usage.input_tokens == 200  # the retry costs tokens too
    retry_messages = fake_llm.calls[1].messages
    assert retry_messages[-1][0] == "user"
    assert "quotes must be a list" in retry_messages[-1][1]
    assert fake_llm.calls[0].messages == retry_messages[:-1]  # same prompt plus the correction


async def test_two_invalid_answers_stop_after_two_calls(fake_llm: FakeLLM):
    fake_llm.script("job_extraction", InvalidOutput(), InvalidOutput(), make_facts())

    with pytest.raises(LLMOutputError) as raised:
        await llm.run("job_extraction", "a posting")

    assert raised.value.error_code == "LLM_OUTPUT_INVALID"
    assert len(fake_llm.calls) == 2  # never loops; the third scripted answer is not used


async def test_a_provider_error_propagates_untouched(fake_llm: FakeLLM):
    fake_llm.script("job_extraction", TimeoutError("provider timed out"))

    with pytest.raises(TimeoutError):
        await llm.run("job_extraction", "a posting")


async def test_a_function_can_build_the_answer_from_the_messages(fake_llm: FakeLLM):
    fake_llm.script(
        "job_extraction",
        lambda messages: make_facts(language="es" if "Desarrollador" in messages[-1][1] else "en"),
    )

    result = await llm.run("job_extraction", "Desarrollador frontend")

    assert isinstance(result.output, JobFacts)
    assert result.output.language == "es"


async def test_the_prompt_sent_has_a_stable_prefix_and_a_fenced_input(fake_llm: FakeLLM):
    fake_llm.script("job_extraction", make_facts(), make_facts())

    await llm.run("job_extraction", "first posting")
    await llm.run("job_extraction", "second posting")

    first, second = fake_llm.calls
    assert first.messages[:-1] == second.messages[:-1]
    assert first.messages[-1][1].startswith("<posting>")


async def test_an_unknown_task_is_a_programming_error(fake_llm: FakeLLM):
    with pytest.raises(KeyError):
        await llm.run("nope", "x")
