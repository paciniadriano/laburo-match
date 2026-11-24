"""Seed the sample profile into the dev database: `make seed`."""

import asyncio
import json
from pathlib import Path

from src.app.profile.seed import seed_sample_profile
from src.config.settings import get_settings
from src.db.session import make_engine, make_session_factory

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "samples" / "sample_evidence.json"


async def main() -> None:
    sample = json.loads(SAMPLE.read_text())  # read before any await: nothing else is running
    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        async with make_session_factory(engine)() as session:
            result = await seed_sample_profile(session, sample, settings.job_max_age_days)
            await session.commit()
    finally:
        await engine.dispose()
    print(
        f"Seeded user 'local': {result.evidence_seeded} evidence items "
        f"({result.languages_skipped} language items skipped until phase 3)."
    )


if __name__ == "__main__":
    asyncio.run(main())
