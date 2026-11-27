import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.profile.seed import seed_sample_profile
from src.db.models import Evidence, Profile, User

SAMPLE: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parents[2] / "data" / "samples" / "sample_evidence.json").read_text()
)


async def _count(session: AsyncSession, table: type) -> int:
    return await session.scalar(select(func.count()).select_from(table)) or 0


async def test_seed_creates_a_complete_profile_with_evidence(session: AsyncSession):
    result = await seed_sample_profile(session, SAMPLE, max_job_age_days=30)

    assert (result.evidence_seeded, result.languages_skipped) == (28, 3)
    assert await _count(session, User) == 1
    assert await _count(session, Profile) == 1
    assert await _count(session, Evidence) == 28
    row = (await session.execute(select(Profile))).scalar_one()
    assert row.is_complete is True
    assert row.constraints["country"] == "AR"
    assert row.exclusions["max_job_age_days"] == 30


async def test_running_the_seed_twice_changes_nothing(session: AsyncSession):
    await seed_sample_profile(session, SAMPLE, max_job_age_days=30)
    ids_before = set(await session.scalars(select(Evidence.id)))

    await seed_sample_profile(session, SAMPLE, max_job_age_days=30)

    assert await _count(session, User) == 1
    assert await _count(session, Evidence) == 28
    assert set(await session.scalars(select(Evidence.id))) == ids_before  # same rows, not new ones


async def test_react_years_are_the_union_of_its_two_periods(session: AsyncSession):
    await seed_sample_profile(session, SAMPLE, max_job_age_days=30)

    react = (await session.execute(select(Evidence).where(Evidence.name == "React"))).scalar_one()

    assert react.years == pytest.approx(7.48, abs=0.01)
    assert react.strength == "detailed"


async def test_a_second_run_picks_up_changed_settings(session: AsyncSession):
    await seed_sample_profile(session, SAMPLE, max_job_age_days=30)

    await seed_sample_profile(session, SAMPLE, max_job_age_days=14)

    # Read the column, not the ORM object: the upsert bypasses the session's memory.
    exclusions = await session.scalar(select(Profile.exclusions))
    assert exclusions == {"max_job_age_days": 14}
