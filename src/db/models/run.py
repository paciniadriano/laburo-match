"""Search runs and the per-job screening state inside each run."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, CreatedAt, UuidPk


class SearchRun(Base):
    """One search (`search`) or one job screened alone (`single`). Users never see the term."""

    __tablename__ = "search_runs"
    __table_args__ = (
        # Postgres only lets a foreign key point at columns that are unique together. This is
        # the target of `run_jobs`' composite key; `id` alone is already unique.
        UniqueConstraint("id", "user_id"),
        Index("ix_search_runs_user_id_created_at", "user_id", "created_at"),
        CheckConstraint("kind IN ('search','single')", name="kind"),
        CheckConstraint("status IN ('running','done')", name="status"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str]
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # stored for audit
    status: Mapped[str] = mapped_column(default="running")
    created_at: Mapped[CreatedAt]
    expires_at: Mapped[datetime]
    # Funnel counters (found, after prefilter, over cap, extracted, cache hits, LLM calls,
    # tokens, cost...). One JSONB object so a new counter never needs a migration.
    funnel: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class RunJob(Base):
    """Screening result of one job in one run; also the queue `screen_batch` claims from."""

    __tablename__ = "run_jobs"
    __table_args__ = (
        # (run_id, user_id) must match a run of that same user: a row can never claim to belong
        # to user B while its run belongs to user A.
        ForeignKeyConstraint(
            ["run_id", "user_id"],
            ["search_runs.id", "search_runs.user_id"],
            ondelete="CASCADE",
            name="fk_run_jobs_run_id_user_id_search_runs",
        ),
        Index("ix_run_jobs_run_id_status", "run_id", "status"),
        # "The user's most recent done row for this job" (staleness checks, list_jobs).
        Index("ix_run_jobs_user_id_job_id_screened_at", "user_id", "job_id", "screened_at"),
        CheckConstraint("status IN ('pending','processing','done','failed')", name="status"),
        CheckConstraint(
            "eligibility IN ('eligible','doubtful','not_eligible')", name="eligibility"
        ),
        CheckConstraint("fit_band IN ('high','medium','low')", name="fit_band"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    user_id: Mapped[uuid.UUID]
    position: Mapped[int]  # display number inside the run ("the 3"); tools never accept it
    status: Mapped[str] = mapped_column(default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    claimed_at: Mapped[datetime | None]
    last_error: Mapped[str] = mapped_column(default="")
    prefilter_reason: Mapped[str] = mapped_column(default="")
    # NULL until screened (or when a prefilter discarded the job before eligibility ran).
    eligibility: Mapped[str | None]
    eligibility_reason: Mapped[str] = mapped_column(default="")
    eligibility_quotes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    recruiter_questions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    profile_questions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    distance_km: Mapped[float | None]
    fit_band: Mapped[str | None]  # filled by matching (phase 5)
    gaps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    flags: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    # Hash of the profile inputs that affect screening; a different one marks the row stale.
    screening_hash: Mapped[str] = mapped_column(default="")
    screened_at: Mapped[datetime | None]
