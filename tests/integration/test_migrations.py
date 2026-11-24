from sqlalchemy import create_engine, inspect

from alembic import command
from src.config.settings import get_settings
from src.db.base import Base
from src.db.migrate import alembic_config
from tests.guards import ensure_test_database


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_migrations_go_up_down_and_up_again():
    url = get_settings().test_database_url
    ensure_test_database(url)
    config = alembic_config(url)
    expected = set(Base.metadata.tables)

    command.downgrade(config, "base")
    assert _tables(url) == set()

    command.upgrade(config, "head")
    assert _tables(url) == expected

    command.downgrade(config, "base")
    assert _tables(url) == set()

    command.upgrade(config, "head")  # leave the database at the latest schema
    assert _tables(url) == expected
