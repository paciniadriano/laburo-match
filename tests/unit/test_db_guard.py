import pytest

from tests.guards import ensure_test_database


def test_accepts_a_test_database():
    ensure_test_database("postgresql+psycopg://u:p@localhost:5432/laburo_test")


@pytest.mark.parametrize("name", ["laburo", "laburo_dev", "test_laburo", "postgres"])
def test_rejects_any_other_database(name: str):
    with pytest.raises(RuntimeError, match="must end in '_test'"):
        ensure_test_database(f"postgresql+psycopg://u:p@localhost:5432/{name}")
