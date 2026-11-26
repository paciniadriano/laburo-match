"""What every MCP tool needs from the running server, and how a call gets its user and session."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

from fastmcp import Context
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.profile.store import find_user_id
from src.config.settings import Settings
from src.core.security import current_subject
from src.sources.base import JobSource


@dataclass(frozen=True)
class AppState:
    """Process-wide objects created at startup. Clients of a pool, never per-request state."""

    sessions: async_sessionmaker[AsyncSession]
    settings: Settings
    sources: list[JobSource]


def app_state(ctx: Context) -> AppState:
    return ctx.lifespan_context["app"]


async def current_user_id(state: AppState) -> UUID:
    """The caller's user id. It comes from the auth context, never from a tool argument."""
    async with state.sessions() as session:
        return await find_user_id(session, current_subject())


@asynccontextmanager
async def user_session(state: AppState) -> AsyncIterator[tuple[AsyncSession, UUID]]:
    """One session and the caller's user id, committed if the block ends without an error."""
    async with state.sessions() as session:
        user_id = await find_user_id(session, current_subject())
        yield session, user_id
        await session.commit()
