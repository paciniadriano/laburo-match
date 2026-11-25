"""Shared fixtures. The database ones always target the separate `_test` database."""

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.app.profile.seed import seed_sample_profile
from src.config.settings import get_settings
from src.db.base import Base
from src.db.migrate import upgrade_to_head
from src.db.session import make_engine
from src.llm import use_backend
from tests.fakes.fake_llm import FakeLLM
from tests.guards import ensure_test_database


@pytest.fixture
def test_database_url() -> str:
    url = get_settings().test_database_url
    ensure_test_database(url)
    return url


@pytest.fixture(scope="session")
def migrated_database() -> None:
    """Bring the test database to the latest schema once per run (a no-op if it already is)."""
    url = get_settings().test_database_url
    ensure_test_database(url)
    upgrade_to_head(url)


@pytest.fixture
async def engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    # NullPool: one fresh connection per use, so nothing is shared between tests or event loops.
    engine = make_engine(test_database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine, migrated_database: None) -> AsyncIterator[AsyncSession]:
    """Default DB fixture: everything the test does is rolled back at the end.

    The session joins an outer transaction through a SAVEPOINT, so the code under test can call
    `commit()` freely: it only releases the savepoint and the outer rollback still undoes it.
    """
    async with engine.connect() as connection:
        outer = await connection.begin()
        factory = async_sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with factory() as session:
            yield session
        await outer.rollback()


@pytest.fixture(autouse=True)
def fake_llm() -> Iterator[FakeLLM]:
    """Every test gets a strict FakeLLM, so no test can reach a real provider by accident."""
    fake = FakeLLM()
    with use_backend(fake):
        yield fake


SAMPLE_EVIDENCE = Path(__file__).resolve().parents[1] / "data" / "samples" / "sample_evidence.json"


@pytest.fixture
async def user_id(session: AsyncSession) -> uuid.UUID:
    """The seeded `local` user: a complete fictional profile (AR, remote, frontend roles)."""
    sample = json.loads(SAMPLE_EVIDENCE.read_text())
    return (await seed_sample_profile(session, sample, max_job_age_days=30)).user_id


@pytest.fixture
async def committed_sessions(
    engine: AsyncEngine, migrated_database: None
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """For tests that need several connections seeing each other's committed data.

    Everything really commits here, so every table is emptied afterwards. The `_test` guard in
    `test_database_url` is what makes that safe to do.
    """
    yield async_sessionmaker(bind=engine, expire_on_commit=False)
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
