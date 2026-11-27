import threading
import time

from src.config.settings import get_settings
from src.db.startup import migration_lock, run_startup
from tests.guards import ensure_test_database


def test_two_starters_never_hold_the_lock_at_the_same_time():
    url = get_settings().test_database_url
    ensure_test_database(url)
    intervals: list[tuple[float, float]] = []

    def starter() -> None:
        with migration_lock(url, poll_seconds=0.02):
            entered = time.monotonic()
            time.sleep(0.3)  # pretend to migrate: long enough to overlap if the lock failed
            intervals.append((entered, time.monotonic()))

    threads = [threading.Thread(target=starter) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    first, second = sorted(intervals)
    assert len(intervals) == 2
    assert first[1] <= second[0]  # the first one left before the second one entered


def test_startup_is_idempotent_on_an_already_migrated_database():
    url = get_settings().test_database_url
    ensure_test_database(url)

    run_startup(url)
    run_startup(url)  # a second container starting later must not fail or change anything
