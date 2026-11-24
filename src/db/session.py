"""Async engine and session factory.

The engine is the connection pool: one per process, created at startup. A session is one short
conversation with the database. Rule of the project: one session per concurrent task, never
shared inside `asyncio.gather`.
"""

from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(url: str, **kwargs: Any) -> AsyncEngine:
    """Create the pool. `pool_pre_ping` replaces a connection the server closed while idle."""
    return create_async_engine(url, pool_pre_ping=True, **kwargs)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: after a commit, attributes stay readable. Otherwise the next read
    # would try to reload them lazily, which cannot happen outside an `await` in async code.
    return async_sessionmaker(engine, expire_on_commit=False)
