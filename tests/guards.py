"""Safety checks for the test suite."""

from sqlalchemy.engine import make_url


def ensure_test_database(url: str) -> None:
    """Abort unless the database name ends in `_test`: the real profile is never touched."""
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests on database {name!r}: its name must end in '_test'."
        )
