from datetime import UTC, datetime, timedelta

import httpx

from src.config.settings import Settings
from src.core import clock
from src.sources.base import SourceQuery
from src.sources.getonbrd import GetOnBoardReplay, GetOnBoardSource
from src.sources.registry import GETONBRD_RECORDING, build_sources

QUERY = SourceQuery(categories=("programming",), max_jobs=500)


async def test_every_recorded_job_parses_so_the_adapter_understands_the_real_api_shape():
    result = await GetOnBoardReplay(GETONBRD_RECORDING).fetch(QUERY)

    assert len(result.jobs) == 30
    assert result.warnings == []  # no malformed job among the real ones
    for job in result.jobs:
        assert job.url.startswith("https://www.getonbrd.com/jobs/")  # attribution link
        assert job.title and job.company and job.language
        assert "[description]" in job.body
        assert "<" not in job.body  # HTML never reaches the LLM


async def test_the_newest_recorded_job_reads_as_published_now_and_relative_ages_are_kept():
    recorded = (await GetOnBoardReplay(GETONBRD_RECORDING).fetch(QUERY)).jobs
    far_future = datetime(2027, 6, 1, 12, 0, tzinfo=UTC)

    with clock.freeze(far_future):
        shifted = (await GetOnBoardReplay(GETONBRD_RECORDING).fetch(QUERY)).jobs

    dates = [job.posted_at for job in shifted if job.posted_at]
    assert max(dates) == far_future
    original = [job.posted_at for job in recorded if job.posted_at]
    # Every job moved by the same amount: the gaps between them are untouched.
    gaps_before = sorted(max(original) - d for d in original)
    gaps_after = sorted(max(dates) - d for d in dates)
    assert gaps_before == gaps_after
    assert max(dates) - min(dates) < timedelta(days=60)


async def test_max_jobs_limits_the_replay():
    result = await GetOnBoardReplay(GETONBRD_RECORDING).fetch(SourceQuery(("programming",), 5))

    assert len(result.jobs) == 5


def test_demo_mode_uses_the_recording_and_normal_mode_uses_the_real_api():
    base = Settings.from_env_file(None)
    client = httpx.AsyncClient()

    demo = build_sources(base.model_copy(update={"demo_mode": True}), client)
    live = build_sources(base.model_copy(update={"demo_mode": False}), client)

    assert [type(source) for source in demo] == [GetOnBoardReplay]
    assert [type(source) for source in live] == [GetOnBoardSource]
