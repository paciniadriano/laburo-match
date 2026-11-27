from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.app.jobs.candidate import Candidate
from src.app.search.selection import select_for_screening

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
ROLES = ("Frontend Engineer",)


def job(title: str, days_old: int = 1) -> Candidate:
    return Candidate(uuid4(), title, NOW - timedelta(days=days_old), None)


def test_the_best_titles_go_first_and_the_rest_wait_for_a_later_search():
    front, back, designer = job("Frontend Engineer"), job("Backend Engineer"), job("Designer")

    selection = select_for_screening([designer, back, front], ROLES, NOW, 30, limit=2)

    assert selection.to_screen == [front, back]
    assert selection.left_for_later == [designer]
    assert selection.discarded == []


def test_old_jobs_are_discarded_with_their_reason_and_never_count_toward_the_cap():
    fresh, old = job("Frontend Engineer"), job("Frontend Engineer", days_old=45)

    selection = select_for_screening([old, fresh], ROLES, NOW, 30, limit=1)

    assert selection.to_screen == [fresh]
    assert selection.discarded == [(old, "too_old")]
    assert selection.discard_counts == {"too_old": 1}
    assert selection.left_for_later == []


def test_nothing_new_gives_an_empty_selection():
    selection = select_for_screening([], ROLES, NOW, 30, limit=10)

    assert (selection.to_screen, selection.discarded, selection.left_for_later) == ([], [], [])


# --- duplicates -----------------------------------------------------------------------------
def posting(title: str, company: str, days_old: int | None, location: str = "Remote") -> Candidate:
    posted = None if days_old is None else NOW - timedelta(days=days_old)
    return Candidate(uuid4(), title, posted, None, "remote", location, "", company)


def test_the_same_opening_posted_twice_keeps_only_the_newest():
    old = posting("Full-Stack Developer", "bc tecnologia", days_old=9)
    new = posting("Full-stack  developer", "bc tecnologia", days_old=2)  # case and spaces differ

    selection = select_for_screening([old, new], ROLES, NOW, 30, limit=10)

    assert selection.to_screen == [new]
    assert selection.discarded == [(old, "duplicate")]


def test_postings_that_differ_in_employer_or_place_are_different_openings():
    jobs = [
        posting("Full-Stack Developer", "acme", 1),
        posting("Full-Stack Developer", "globex", 1),  # another employer
        posting("Full-Stack Developer", "acme", 1, location="Chile"),  # another place
    ]

    assert len(select_for_screening(jobs, ROLES, NOW, 30, limit=10).to_screen) == 3


def test_without_an_employer_name_two_postings_are_never_merged():
    jobs = [posting("Full-Stack Developer", "", 1), posting("Full-Stack Developer", "", 3)]

    assert len(select_for_screening(jobs, ROLES, NOW, 30, limit=10).to_screen) == 2


def test_a_dated_posting_wins_over_an_undated_copy():
    undated = posting("Full-Stack Developer", "acme", None)
    dated = posting("Full-Stack Developer", "acme", 5)

    selection = select_for_screening([undated, dated], ROLES, NOW, 30, limit=10)

    assert selection.to_screen == [dated]
