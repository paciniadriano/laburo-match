"""Container-start routine: migrations, then checkpointer setup, under one advisory lock."""
import os
import sys
import time

import psycopg
from alembic import command
from alembic.config import Config
from langgraph.checkpoint.postgres import PostgresSaver

LOCK_KEY = 727_001  # arbitrary app-wide constant
who = sys.argv[1]
url = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
t0 = time.time()


def log(msg: str) -> None:
    print(f"[{who}] +{time.time() - t0:5.2f}s {msg}", flush=True)


# The lock belongs to this connection and is released when it closes (even on a crash).
with psycopg.connect(url, autocommit=True) as lock_conn:
    log("waiting for lock")
    # Poll with the non-blocking variant. A blocking pg_advisory_lock() keeps a statement
    # open, and the holder's CREATE INDEX CONCURRENTLY (inside checkpointer setup) waits for
    # every open statement to finish: a deadlock Postgres cannot detect.
    while not lock_conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()[0]:
        time.sleep(0.2)
    log("lock acquired")
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "alembic.ini")), "head")
    log("alembic done")
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
    log("checkpointer setup done")
    time.sleep(1)  # hold the lock long enough to make the race visible
    lock_conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
    log("lock released")
