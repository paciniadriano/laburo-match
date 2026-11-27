from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.jobs.extraction import extract_job_facts, posting_text
from src.app.jobs.store import upsert_shared_jobs
from src.config.constants import JOB_TEXT_MAX_CHARS
from src.db.models import Job, JobExtraction
from tests.factories import make_facts, make_restriction, make_source_job
from tests.fakes.fake_llm import FakeLLM

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


async def _store_job(session: AsyncSession, **changes) -> Job:
    (candidate,) = await upsert_shared_jobs(session, [make_source_job("a", **changes)], NOW)
    return await session.get_one(Job, candidate.job_id)


async def test_a_miss_calls_the_llm_once_and_stores_the_facts(
    session: AsyncSession, fake_llm: FakeLLM
):
    job = await _store_job(session)
    fake_llm.script("job_extraction", make_facts(language="es"))

    extracted = await extract_job_facts(session, job)

    assert not extracted.from_cache
    assert extracted.facts.language == "es"
    assert extracted.usage.input_tokens == 100
    assert await session.scalar(select(func.count()).select_from(JobExtraction)) == 1


async def test_a_cached_job_costs_zero_llm_calls(session: AsyncSession, fake_llm: FakeLLM):
    job = await _store_job(session)
    fake_llm.script("job_extraction", make_facts(language="es"))
    await extract_job_facts(session, job)
    calls_after_first = len(fake_llm.calls)

    again = await extract_job_facts(session, job)  # nothing scripted: a call would fail loudly

    assert again.from_cache
    assert again.facts.language == "es"
    assert again.usage.input_tokens == 0
    assert len(fake_llm.calls) == calls_after_first


async def test_changed_posting_text_is_extracted_again(session: AsyncSession, fake_llm: FakeLLM):
    job = await _store_job(session)
    fake_llm.script("job_extraction", make_facts(language="es"), make_facts(language="pt"))
    await extract_job_facts(session, job)

    (candidate,) = await upsert_shared_jobs(
        session, [make_source_job("a", body="[description]\nA different posting")], NOW
    )
    changed = await session.get_one(Job, candidate.job_id, populate_existing=True)
    again = await extract_job_facts(session, changed)

    assert not again.from_cache
    assert again.facts.language == "pt"


async def test_a_changed_llm_setup_invalidates_the_cache(
    session: AsyncSession, fake_llm: FakeLLM, monkeypatch
):
    job = await _store_job(session)
    fake_llm.script("job_extraction", make_facts(), make_facts())
    await extract_job_facts(session, job)

    monkeypatch.setenv("LLM_BASE_MODEL", "another-model")
    from src.config.settings import get_settings

    get_settings.cache_clear()
    try:
        again = await extract_job_facts(session, job)
    finally:
        get_settings.cache_clear()

    assert not again.from_cache


async def test_quotes_the_model_made_up_are_dropped_before_caching(
    session: AsyncSession, fake_llm: FakeLLM
):
    job = await _store_job(session, body="[description]\nOpen to candidates in Chile only")
    invented = make_restriction(quotes=["US citizens only"])  # not in the posting
    fake_llm.script("job_extraction", make_facts(restrictions=[invented]))

    first = await extract_job_facts(session, job)
    cached = await extract_job_facts(session, job)

    assert first.facts.restrictions[0].quotes == []
    assert first.facts.restrictions[0].evidence_kind == "inferred"
    assert cached.facts == first.facts  # the cache holds the verified version


async def test_the_text_sent_to_the_model_is_capped(session: AsyncSession):
    job = await _store_job(session, body="x" * (JOB_TEXT_MAX_CHARS * 2))

    assert len(posting_text(job)) == JOB_TEXT_MAX_CHARS


async def test_a_changed_size_cap_re_extracts_only_the_postings_it_cut(
    session: AsyncSession, fake_llm: FakeLLM, monkeypatch
):
    short = await _store_job(session, body="[description]\nShort posting")
    (long_candidate,) = await upsert_shared_jobs(
        session, [make_source_job("long", body="x" * 500)], NOW
    )
    long = await session.get_one(Job, long_candidate.job_id)
    monkeypatch.setattr("src.app.jobs.extraction.JOB_TEXT_MAX_CHARS", 300)
    fake_llm.script("job_extraction", make_facts(), make_facts())
    await extract_job_facts(session, short)
    await extract_job_facts(session, long)  # cut to 300 characters

    monkeypatch.setattr("src.app.jobs.extraction.JOB_TEXT_MAX_CHARS", 1000)
    fake_llm.script("job_extraction", make_facts())

    assert (await extract_job_facts(session, short)).from_cache  # it fitted either way
    assert not (await extract_job_facts(session, long)).from_cache  # it can now be read whole
