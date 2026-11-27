"""Importing this package registers every table on `Base.metadata` (Alembic relies on it)."""

from src.db.models.job import Job, JobExtraction
from src.db.models.profile import Evidence, Profile, User
from src.db.models.run import RunJob, SearchRun

__all__ = ["Evidence", "Job", "JobExtraction", "Profile", "RunJob", "SearchRun", "User"]
