"""Read the user's profile."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import ProfileRequiredError
from src.db.models import Profile
from src.models.profile import Constraints


async def load_constraints(session: AsyncSession, user_id: UUID) -> Constraints:
    """The constraints of a complete profile; screening is meaningless without one."""
    profile = await session.get(Profile, user_id)
    if profile is None or not profile.is_complete:
        raise ProfileRequiredError()
    return Constraints.model_validate(profile.constraints)
