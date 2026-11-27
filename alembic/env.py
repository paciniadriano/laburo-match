"""Alembic environment: which database to migrate and which tables belong to us."""

from sqlalchemy import create_engine

import src.db.models  # noqa: F401  (registers every table on Base.metadata)
from alembic import context
from src.config.settings import get_settings
from src.db.base import Base

config = context.config

# Tables created by LangGraph's PostgresSaver.setup() (phase 6). Alembic must not manage them.
CHECKPOINTER_TABLES = {
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
}


def database_url() -> str:
    """Priority: set from code (tests, startup) > `-x url=...` on the CLI > settings."""
    return (
        config.attributes.get("url")
        or context.get_x_argument(as_dictionary=True).get("url")
        or get_settings().database_url
    )


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    return not (type_ == "table" and name in CHECKPOINTER_TABLES)


def run_migrations() -> None:
    # A synchronous engine on purpose: migrations run from startup scripts and test fixtures,
    # where an `asyncio.run` inside Alembic would collide with an already running event loop.
    engine = create_engine(database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
