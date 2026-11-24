"""One test per rule of the eligibility definitions in CLAUDE.md. The profile is Argentine."""

import pytest

from src.app.eligibility.result import DISCLAIMER
from src.app.eligibility.rules import evaluate_eligibility
from src.models.profile import Constraints
from tests.factories import make_facts, make_restriction

AR = Constraints(country="AR", citizenships=["AR"], work_authorizations=["AR"])
LATAM = make_restriction(quotes=["Remote within Latin America"], places=["Latin America"])
US_ONLY = make_restriction(
    quotes=["You must live in any US state"], places=["any US state"], place_scope="countries"
)


def verdict(restrictions, constraints: Constraints = AR, **facts):
    return evaluate_eligibility(make_facts(restrictions=restrictions, **facts), constraints)


# --- eligible ------------------------------------------------------------------------------
def test_an_explicit_location_that_includes_the_users_country_and_nothing_else_is_eligible():
    result = verdict([LATAM])

    assert result.verdict == "eligible"
    assert result.quotes == ["Remote within Latin America"]
    assert "Argentina" in result.reason


def test_a_timezone_requirement_is_a_warning_and_does_not_block():
    overlap = make_restriction(
        kind="timezone",
        quotes=["At least five working hours of overlap with Pacific Time"],
        places=[],
        place_scope="not_applicable",
    )

    result = verdict([LATAM, overlap])

    assert result.verdict == "eligible"
    assert result.warnings == [
        'Working hours: "At least five working hours of overlap with Pacific Time"'
    ]


def test_an_inferred_hint_that_includes_the_country_is_not_a_compatible_signal():
    hint = make_restriction(evidence_kind="inferred", quotes=[])

    assert verdict([hint]).verdict == "doubtful"  # nothing explicit says where you can work from


# --- not_eligible --------------------------------------------------------------------------
def test_an_explicit_location_that_excludes_the_users_country_is_not_eligible():
    result = verdict([US_ONLY])

    assert result.verdict == "not_eligible"
    assert result.quotes == ["You must live in any US state"]
    assert "Argentina" in result.reason and "any US state" in result.reason


def test_one_unmet_restriction_is_enough_even_if_another_is_met():
    assert verdict([LATAM, US_ONLY]).verdict == "not_eligible"


def test_a_certain_no_outweighs_doubts_elsewhere():
    doubt = make_restriction(kind="visa", quotes=["B1/B2 visa required"], places=[])

    assert verdict([US_ONLY, doubt]).verdict == "not_eligible"


def test_a_restriction_contradicted_by_another_statement_is_not_enough_to_say_no():
    contradiction = make_restriction(
        evidence_kind="contradictory",
        quotes=["Open to candidates in Argentina", "US residents only"],
        places=[],
    )

    result = verdict([US_ONLY, contradiction])

    assert result.verdict == "doubtful"


def test_a_place_with_a_known_country_and_an_unknown_one_is_never_a_hard_no():
    mixed = make_restriction(places=["Chile", "Narnia"], quotes=["Chile or Narnia"])

    assert verdict([mixed]).verdict == "doubtful"


def test_the_same_restriction_with_only_known_places_is_a_hard_no():
    known = make_restriction(places=["Chile", "Bolivia"], quotes=["Chile or Bolivia"])

    assert verdict([known]).verdict == "not_eligible"


# --- doubtful ------------------------------------------------------------------------------
def test_no_restrictions_at_all_is_doubtful_with_a_question_for_the_recruiter():
    result = verdict([])

    assert result.verdict == "doubtful"
    assert "nothing about where" in result.reason
    assert result.recruiter_questions == ["Can this role be done from Argentina?"]


def test_an_inferred_restriction_that_excludes_the_country_can_only_make_it_doubtful():
    inferred_us = make_restriction(
        evidence_kind="inferred", quotes=["401k and US benefits"], places=["US"]
    )

    assert verdict([LATAM, inferred_us]).verdict == "doubtful"


def test_a_contradiction_is_doubtful_and_shows_both_quotes():
    contradiction = make_restriction(
        kind="modality",
        evidence_kind="contradictory",
        quotes=["100% remote", "hybrid in Las Condes"],
        places=[],
    )

    result = verdict([LATAM, contradiction])

    assert result.verdict == "doubtful"
    assert "100% remote" in result.quotes and "hybrid in Las Condes" in result.quotes
    assert result.recruiter_questions


@pytest.mark.parametrize("kind", ["visa", "citizenship", "work_authorization"])
def test_an_explicit_requirement_the_code_cannot_compare_yet_keeps_the_job_doubtful(kind: str):
    unchecked = make_restriction(kind=kind, quotes=["Must hold a US work permit"], places=[])

    result = verdict([LATAM, unchecked])

    assert result.verdict == "doubtful"
    assert "not checked yet" in result.reason
    assert result.quotes == ["Must hold a US work permit"]


def test_an_inferred_requirement_the_code_cannot_compare_is_only_a_warning():
    inferred = make_restriction(kind="visa", evidence_kind="inferred", quotes=[], places=[])

    result = verdict([LATAM, inferred])

    assert result.verdict == "eligible"
    assert "inferred" in result.warnings[0]


@pytest.mark.parametrize("place", ["Worldwide", "Americas"])
def test_ambiguous_places_are_doubtful_not_eligible(place: str):
    result = verdict([make_restriction(places=[place], quotes=[f"Open to {place}"])])

    assert result.verdict == "doubtful"
    assert result.recruiter_questions == ["Is the role open to candidates living in Argentina?"]


def test_a_worldwide_scope_given_by_the_model_is_ambiguous_even_with_a_country_named():
    scoped = make_restriction(places=["Chile"], place_scope="worldwide", quotes=["Anywhere"])

    assert verdict([scoped]).verdict == "doubtful"


def test_an_unknown_profile_country_asks_the_user_instead_of_guessing():
    result = verdict([LATAM], constraints=Constraints())

    assert result.verdict == "doubtful"
    assert result.profile_questions == ["Which country do you live in?"]


@pytest.mark.parametrize("modality", ["hybrid", "onsite"])
def test_office_jobs_stay_doubtful_until_distances_are_checked(modality: str):
    result = verdict([LATAM], work_modality=modality)

    assert result.verdict == "doubtful"
    assert "not checked yet" in result.reason


def test_an_explicit_location_that_excludes_the_country_wins_over_the_office_doubt():
    assert verdict([US_ONLY], work_modality="hybrid").verdict == "not_eligible"


def test_a_text_that_is_not_a_job_posting_is_doubtful():
    result = evaluate_eligibility(make_facts(is_job_posting=False), AR)

    assert result.verdict == "doubtful"
    assert "does not look like a job posting" in result.reason


def test_the_disclaimer_is_available_to_attach_to_every_card():
    assert "not legal advice" in DISCLAIMER


def test_an_ordinary_contract_type_is_a_badge_and_does_not_change_the_verdict():
    contractor = make_restriction(
        kind="payroll",
        quotes=["This is a long-term independent contractor engagement"],
        places=[],
    )

    result = verdict([LATAM, contractor])

    assert result.verdict == "eligible"
    assert result.warnings == [
        'Contract type: "This is a long-term independent contractor engagement"'
    ]


@pytest.mark.parametrize(
    "phrase", ["W2 employees only", "Paid as a 1099 contractor", "Valid SSN required"]
)
def test_a_us_specific_payroll_phrase_keeps_the_job_doubtful(phrase: str):
    us_payroll = make_restriction(kind="payroll", quotes=[phrase], places=[])

    result = verdict([LATAM, us_payroll])

    assert result.verdict == "doubtful"
    assert result.quotes == [phrase]


def test_a_word_that_merely_contains_a_marker_is_not_us_payroll():
    unrelated = make_restriction(kind="payroll", quotes=["Pay in 10990 pesos"], places=[])

    assert verdict([LATAM, unrelated]).verdict == "eligible"
