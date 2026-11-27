"""Declarative base, shared column types and naming rules for every table."""

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, mapped_column

from src.core import clock

# Explicit constraint names make migrations predictable: Alembic can drop "ck_jobs_source"
# by name instead of guessing a name Postgres generated.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Every datetime in the project is timezone-aware.
    type_annotation_map = {datetime: DateTime(timezone=True)}


# UUID primary keys are generated in Python, so an object has its id before it is flushed.
UuidPk = Annotated[uuid.UUID, mapped_column(primary_key=True, default=uuid.uuid4)]
# Timestamps come from the project clock, never from the database `now()`.
CreatedAt = Annotated[datetime, mapped_column(default=clock.now)]
