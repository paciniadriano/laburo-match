"""The only source of "now" for the whole project.

Code asks `now()` instead of calling `datetime.now()`, and SQL receives that value as a `:now`
parameter instead of using the database `now()`. Tests then control time: a claim that is 6
minutes old is "stale" because the test says so, not because it waited 6 minutes.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

# A ContextVar (not a plain global) so frozen time follows the running task and its children
# and never leaks between concurrent tests.
_frozen: ContextVar[datetime | None] = ContextVar("frozen_now", default=None)


def now() -> datetime:
    """Current UTC time, timezone-aware; the frozen value while `freeze()` is active."""
    frozen = _frozen.get()
    return frozen if frozen is not None else datetime.now(UTC)


@contextmanager
def freeze(at: datetime) -> Iterator[None]:
    """Make `now()` return `at` inside the `with` block. For tests."""
    if at.tzinfo is None:
        raise ValueError("freeze() needs a timezone-aware datetime")
    token = _frozen.set(at)
    try:
        yield
    finally:
        _frozen.reset(token)
