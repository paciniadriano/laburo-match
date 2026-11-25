"""Job postings and the cache of facts extracted from them."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, CreatedAt, UuidPk


class Job(Base):
    """A job posting. Shared when it comes from a source, private when the user pasted it."""

    __tablename__ = "jobs"
    __table_args__ = (
        # Two kinds of identity, so two partial unique indexes, each with its own WHERE.
        Index(
            "uq_jobs_source_external_id_shared",
            "source",
            "external_id",
            unique=True,
            postgresql_where=text("owner_user_id IS NULL"),
        ),
        Index(
            "uq_jobs_owner_user_id_content_hash_pasted",
            "owner_user_id",
            "content_hash",
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
        Index("ix_jobs_fingerprint", "fingerprint"),
        CheckConstraint("source IN ('google_jobs','getonbrd','pasted')", name="source"),
    )

    id: Mapped[UuidPk]
    source: Mapped[str]
    external_id: Mapped[str]
    # NULL = comes from a source and is shared; set = pasted by that user and private.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(default="")
    apply_url: Mapped[str] = mapped_column(default="")
    company: Mapped[str] = mapped_column(default="")
    company_normalized: Mapped[str] = mapped_column(default="")
    company_domain: Mapped[str] = mapped_column(default="")
    title: Mapped[str]
    location_text: Mapped[str] = mapped_column(default="")
    raw_text: Mapped[str]
    content_hash: Mapped[str]
    language: Mapped[str] = mapped_column(default="")
    posted_at: Mapped[datetime | None]
    first_seen_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    closed_at: Mapped[datetime | None]
    # Normalized company + title + location, for cross-portal dedupe (phase 4).
    fingerprint: Mapped[str] = mapped_column(default="")
    # NULL on canonical rows; a duplicate points straight to its canonical (no chains).
    canonical_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"))


class JobExtraction(Base):
    """Cache of `JobFacts` per job, valid while the text and the LLM setup are unchanged."""

    __tablename__ = "job_extractions"
    __table_args__ = (CheckConstraint("status IN ('ok','failed')", name="status"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    # version_hash changes when prompt, examples, schema or model change; content_hash when
    # the posting text changes. Either one invalidates the cached row.
    version_hash: Mapped[str] = mapped_column(primary_key=True)
    content_hash: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[str]
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # How much of the posting the model read (the text is capped). Valid only while the text we
    # would send today has this same length: a changed cap re-extracts what it cut, nothing else.
    chars_read: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[CreatedAt]
