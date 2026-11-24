from datetime import UTC, datetime, timedelta

import pytest

from src.core import clock


def test_now_is_timezone_aware_utc():
    assert clock.now().tzinfo is UTC


def test_freeze_fixes_time_and_restores_it_after():
    frozen = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)

    with clock.freeze(frozen):
        assert clock.now() == frozen

    assert clock.now() != frozen


def test_stale_claim_is_decided_by_the_frozen_clock():
    """The example from the design: a claim from 09:50 is stale at 10:00 with a 5-minute limit."""
    claimed_at = datetime(2026, 11, 24, 9, 50, tzinfo=UTC)
    stale_after = timedelta(seconds=300)

    with clock.freeze(datetime(2026, 11, 24, 10, 0, tzinfo=UTC)):
        assert clock.now() - claimed_at > stale_after
    with clock.freeze(datetime(2026, 11, 24, 9, 54, tzinfo=UTC)):
        assert clock.now() - claimed_at <= stale_after


def test_freeze_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        with clock.freeze(datetime(2026, 11, 24, 10, 0)):
            pass
