"""The two wrappers an eval run puts around the real backend: the cache and the budget."""

from pathlib import Path

import pytest

from src import llm
from src.core.errors import BudgetExceededError
from src.core.usage import BudgetGuard
from src.llm.backend import Usage
from src.llm.budget import BudgetedBackend
from src.llm.eval_cache import CachingBackend
from src.llm.tasks import JOB_EXTRACTION
from tests.factories import make_facts
from tests.fakes.fake_llm import FakeLLM, InvalidOutput

TASK = JOB_EXTRACTION.name


def _stored_answers(directory: Path) -> int:
    return len(list(directory.glob("*.json")))


async def test_an_identical_request_is_answered_from_disk_and_costs_nothing(tmp_path: Path):
    fake = FakeLLM(usage=Usage(input_tokens=500, output_tokens=50))
    fake.script(TASK, make_facts())
    cache = CachingBackend(fake, tmp_path)

    with llm.use_backend(cache):
        first = await llm.run(TASK, "posting A")
        second = await llm.run(TASK, "posting A")

    assert first.output == second.output
    assert (cache.hits, cache.misses) == (1, 1)
    assert len(fake.calls) == 1  # the second call never reached the provider
    assert second.usage == Usage()


async def test_a_different_posting_is_a_different_request(tmp_path: Path):
    fake = FakeLLM()
    fake.script(TASK, make_facts(), make_facts())
    cache = CachingBackend(fake, tmp_path)

    with llm.use_backend(cache):
        await llm.run(TASK, "posting A")
        await llm.run(TASK, "posting B")

    assert (cache.hits, cache.misses) == (0, 2)


async def test_an_invalid_answer_is_not_cached(tmp_path: Path):
    fake = FakeLLM()
    fake.script(TASK, InvalidOutput(), make_facts())
    cache = CachingBackend(fake, tmp_path)

    with llm.use_backend(cache):
        result = await llm.run(TASK, "posting A")  # first answer invalid, the retry is good

    assert result.attempts == 2
    assert _stored_answers(tmp_path) == 1  # only the good one was stored


async def test_the_budget_counts_real_calls_and_stops_the_next_one():
    fake = FakeLLM(usage=Usage(input_tokens=1_000_000, output_tokens=0))  # $0.10 per call
    fake.script(TASK, make_facts(), make_facts())
    guard = BudgetGuard(limit_usd=0.05)

    with llm.use_backend(BudgetedBackend(fake, guard)):
        await llm.run(TASK, "posting A")
        with pytest.raises(BudgetExceededError):
            await llm.run(TASK, "posting B")

    assert guard.spent_usd == pytest.approx(0.10)
    assert len(fake.calls) == 1


async def test_cache_hits_do_not_spend_budget(tmp_path: Path):
    fake = FakeLLM(usage=Usage(input_tokens=1_000_000, output_tokens=0))
    fake.script(TASK, make_facts())
    guard = BudgetGuard(limit_usd=0.15)
    # The cache sits outside the budget: what it answers never reaches the counter.
    backend = CachingBackend(BudgetedBackend(fake, guard), tmp_path)

    with llm.use_backend(backend):
        for _ in range(5):
            await llm.run(TASK, "same posting")

    assert guard.spent_usd == pytest.approx(0.10)
