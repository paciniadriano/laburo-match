import os

from alembic import context
from sqlalchemy import create_engine

from models import Base

URL = os.environ["TEST_DATABASE_URL"]
# Tables created by LangGraph's PostgresSaver.setup(); Alembic must not manage them.
CHECKPOINTER_TABLES = {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}


def include_object(obj, name, type_, reflected, compare_to):
    if os.environ.get("PROTECT_CHECKPOINTER") == "1" and type_ == "table" and name in CHECKPOINTER_TABLES:
        return False
    return True


with create_engine(URL).connect() as conn:
    context.configure(connection=conn, target_metadata=Base.metadata, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()
