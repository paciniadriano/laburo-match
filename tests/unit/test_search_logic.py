from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.app.jobs.candidate import Candidate
from src.app.search.plan import build_plan
from src.app.search.prefilter import office_abroad, prefilter_reason, residence_abroad
from src.app.search.relevance import rank
from src.core.relevance import title_relevance
from src.models.profile import Preferences

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
ROLES = ("Frontend Engineer", "Full-Stack Developer")


def candidate(title: str, days_old: int | None = 1, closed: bool = False) -> Candidate:
    return Candidate(
        job_id=uuid4(),
        title=title,
        posted_at=None if days_old is None else NOW - timedelta(days=days_old),
        closed_at=NOW if closed else None,
    )


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Frontend Engineer", 2),
        ("Frontend Developer", 2),  # developer = engineer
        ("Desarrollador Frontend", 2),  # and so is the Spanish word
        ("Senior Frontend Engineer", 2),  # seniority says nothing about the role
        ("Backend Engineer", 1),  # shares only "engineer"
        ("Product Designer", 0),
    ],
)
def test_title_relevance_counts_shared_role_words(title: str, expected: int):
    assert title_relevance(title, ROLES) == expected


def test_without_target_roles_every_title_is_equally_relevant():
    assert title_relevance("Frontend Engineer", ()) == 0


def test_rank_puts_relevant_titles_first_then_newer_ones_then_undated_ones():
    designer = candidate("Product Designer", days_old=0)
    old_frontend = candidate("Frontend Developer", days_old=20)
    new_frontend = candidate("Frontend Engineer", days_old=2)
    undated_frontend = candidate("Frontend Engineer", days_old=None)
    backend = candidate("Backend Engineer", days_old=1)

    ranked = rank([designer, old_frontend, backend, undated_frontend, new_frontend], ROLES)

    assert ranked == [new_frontend, old_frontend, undated_frontend, backend, designer]


def test_rank_without_roles_is_just_newest_first():
    older, newer = candidate("A", days_old=5), candidate("B", days_old=1)

    assert rank([older, newer], ()) == [newer, older]


@pytest.mark.parametrize(
    ("days_old", "closed", "expected"),
    [
        (1, False, None),
        (30, False, None),  # exactly at the limit is still fresh
        (31, False, "too_old"),
        (None, False, None),  # no date: never a reason to discard
        (1, True, "closed"),
    ],
)
def test_prefilter_reasons(days_old: int | None, closed: bool, expected: str | None):
    job = candidate("Frontend Engineer", days_old=days_old, closed=closed)

    assert prefilter_reason(job, NOW, max_age_days=30) == expected


def test_a_closed_job_is_reported_as_closed_even_when_it_is_also_old():
    assert prefilter_reason(candidate("X", days_old=90, closed=True), NOW, 30) == "closed"


def test_the_plan_names_its_roles_and_serializes_for_audit():
    plan = build_plan(Preferences(target_roles=["Frontend Engineer"]))

    assert plan.categories == ("programming",)
    assert "Frontend Engineer" in plan.summary()
    assert plan.to_json()["sources"] == {"getonbrd": {"categories": ["programming"]}}


def test_a_plan_without_roles_still_searches():
    plan = build_plan(Preferences(target_roles=None))

    assert plan.target_roles == ()
    assert "any role" in plan.summary()


# --- office abroad -------------------------------------------------------------------------
def at_office(modality: str, location: str, body: str = "3 dias en oficina") -> Candidate:
    return Candidate(uuid4(), "Backend Developer", NOW, None, modality, location, body)


@pytest.mark.parametrize("modality", ["hybrid", "onsite"])
def test_a_job_that_needs_an_office_in_another_country_is_discarded(modality: str):
    assert prefilter_reason(at_office(modality, "Chile"), NOW, 30, "AR") == "office_abroad"


@pytest.mark.parametrize(
    ("job", "why_it_stays"),
    [
        (at_office("hybrid", "Argentina"), "the office is in the user's country"),
        (at_office("hybrid", "Chile, Argentina"), "one of the offices is in the user's country"),
        (at_office("remote", "Chile"), "remote work crosses borders"),
        (at_office("unknown", "Chile"), "the source does not say where the work happens"),
        (at_office("hybrid", "Remote"), "no country is named"),
        (at_office("hybrid", "Narnia"), "a place the table cannot read is never guessed"),
        (at_office("hybrid", ""), "no place at all"),
    ],
)
def test_any_doubt_keeps_the_job_for_screening(job: Candidate, why_it_stays: str):
    assert office_abroad(job, "AR") is False, why_it_stays


def test_without_the_users_country_nothing_is_discarded_for_its_office():
    assert office_abroad(at_office("hybrid", "Chile"), None) is False


# --- remote, but only for other countries ----------------------------------------------------
def remote_for(residence: str, body: str = "Trabajo 100% remoto") -> Candidate:
    return Candidate(
        uuid4(), "Backend Developer", NOW, None, "remote", "Remote", body, "", residence
    )


def test_a_remote_job_only_for_people_in_other_countries_is_discarded():
    assert prefilter_reason(remote_for("Chile"), NOW, 30, "AR") == "residence_abroad"
    assert prefilter_reason(remote_for("Chile, Peru"), NOW, 30, "AR") == "residence_abroad"


@pytest.mark.parametrize(
    ("job", "why_it_stays"),
    [
        (remote_for("Chile, Argentina, Peru"), "the user's country is one of the listed ones"),
        (remote_for("anywhere"), "fully remote: anyone may apply"),
        (remote_for(""), "the source does not say who may apply"),
        (remote_for("Narnia"), "a place the table cannot read is never guessed"),
    ],
)
def test_a_remote_job_stays_when_there_is_any_doubt(job: Candidate, why_it_stays: str):
    assert residence_abroad(job, "AR") is False, why_it_stays


@pytest.mark.parametrize(
    "job",
    [
        at_office("hybrid", "Chile", "Presencialidad en oficinas de LATAM"),
        remote_for("Mexico", "allowing flexibility in work location globally"),  # Niuro
    ],
)
def test_the_employers_policy_wins_over_what_the_prose_says(job: Candidate):
    """User decision: a declared office or residence elsewhere is enough, whatever the text."""
    assert prefilter_reason(job, NOW, 30, "AR") in {"office_abroad", "residence_abroad"}
