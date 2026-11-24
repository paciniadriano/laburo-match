"""Shared fixtures. The database ones always target the separate `_test` database."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.config.settings import get_settings
from src.db.migrate import upgrade_to_head
from src.db.session import make_engine
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
