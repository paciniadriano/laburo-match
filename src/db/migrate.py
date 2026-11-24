"""Programmatic access to Alembic, shared by the container startup and the tests."""

from pathlib import Path

from alembic.config import Config

from alembic import command

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def alembic_config(url: str) -> Config:
    config = Config(str(_ALEMBIC_INI))
    config.attributes["url"] = url
    return config


def upgrade_to_head(url: str) -> None:
    command.upgrade(alembic_config(url), "head")
