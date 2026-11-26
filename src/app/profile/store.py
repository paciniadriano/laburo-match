"""Read the user's profile."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import ProfileRequiredError
from src.db.models import Profile, User
from src.models.profile import Constraints


async def load_constraints(session: AsyncSession, user_id: UUID) -> Constraints:
    """The constraints of a complete profile; screening is meaningless without one."""
    profile = await session.get(Profile, user_id)
    if profile is None or not profile.is_complete:
        raise ProfileRequiredError()
    return Constraints.model_validate(profile.constraints)


async def find_user_id(session: AsyncSession, subject: str) -> UUID:
    """The database id of the caller. A caller with no account has no profile either."""
    user_id = await session.scalar(select(User.id).where(User.external_id == subject))
    if user_id is None:
        raise ProfileRequiredError()
    return user_id
