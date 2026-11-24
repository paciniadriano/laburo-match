"""Who the user is: account, profile and CV evidence."""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, CreatedAt, UuidPk


class User(Base):
    __tablename__ = "users"

    id: Mapped[UuidPk]
    # The subject claim from the auth provider; "local" when there is no auth.
    external_id: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[CreatedAt]


class Profile(Base):
    """One row per user. The JSONB blocks are validated by Pydantic models, not by the database."""

    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    exclusions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    writing_style: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Every write is `UPDATE ... WHERE profile_version = :expected` (optimistic concurrency).
    profile_version: Mapped[int] = mapped_column(default=1)
    schema_version: Mapped[int] = mapped_column(default=1)
    is_complete: Mapped[bool] = mapped_column(default=False)


class Evidence(Base):
    """One item of the user's background (E1, E2...). The LLM refers to it only by `label`."""

    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("user_id", "label"),
        Index("ix_evidence_user_id_active", "user_id", "active"),
        CheckConstraint(
            "kind IN ('experience','skill','project','education','certification',"
            "'language','other')",
            name="kind",
        ),
        CheckConstraint("strength IN ('detailed','mention','weak')", name="strength"),
        CheckConstraint("source IN ('cv','user')", name="source"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    label: Mapped[str]  # "E1"
    kind: Mapped[str]
    name: Mapped[str]
    normalized_name: Mapped[str]
    # [[start, end], ...]: a skill used in several jobs has several periods. Years are the
    # union of these intervals, so overlapping experiences never count twice.
    periods: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    years: Mapped[float | None]
    quote: Mapped[str] = mapped_column(default="")
    strength: Mapped[str]
    source: Mapped[str] = mapped_column(default="cv")
    content_hash: Mapped[str]
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[CreatedAt]


__all__ = ["Evidence", "Profile", "User"]
