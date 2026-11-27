"""Container-start routine: migrations under one advisory lock.

With several replicas starting at once, exactly one migrates and the others wait. Run it with
`python -m src.db.startup` (the container entrypoint and `make migrate`).
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from sqlalchemy.engine import make_url

from src.config.constants import MIGRATION_LOCK_KEY
from src.config.settings import get_settings
from src.core.logging import configure_logging
from src.db.migrate import upgrade_to_head

logger = logging.getLogger(__name__)


def _psycopg_url(url: str) -> str:
    """psycopg does not understand SQLAlchemy's `postgresql+psycopg://` driver suffix."""
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


@contextmanager
def migration_lock(
    url: str, timeout_seconds: float = 120, poll_seconds: float = 0.2
) -> Iterator[None]:
    """Hold the startup lock while the block runs."""
    # The lock belongs to this connection: Postgres releases it if the process dies.
    with psycopg.connect(_psycopg_url(url), autocommit=True) as connection:
        # Real elapsed time on purpose: this is a wait, not business time (`core.clock`).
        deadline = time.monotonic() + timeout_seconds
        # Poll with the non-blocking variant. A blocking pg_advisory_lock() keeps a statement
        # open, and the holder's own DDL can end up waiting for it: a deadlock Postgres
        # cannot detect.
        while True:
            row = connection.execute("SELECT pg_try_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
            got_it = row.fetchone()
            if got_it is not None and got_it[0]:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("Could not get the migration lock in time")
            time.sleep(poll_seconds)
        try:
            yield
        finally:
            connection.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_KEY,))


def run_startup(url: str) -> None:
    with migration_lock(url):
        logger.info("applying migrations")
        upgrade_to_head(url)
        logger.info("migrations applied")
        # The LangGraph checkpointer `setup()` joins here in phase 6.


if __name__ == "__main__":
    configure_logging()
    run_startup(get_settings().database_url)
