import pytest

from src.config.data.locations import COUNTRIES, REGIONS
from src.core.places import mentions_area, resolve_places


@pytest.mark.parametrize(
    ("place", "must_include", "must_exclude"),
    [
        ("Latin America", {"AR", "BR", "MX"}, {"US", "ES"}),
        ("LATAM", {"AR", "CL"}, {"US"}),
        ("Remote within Latin America", {"AR"}, {"US"}),  # filler words around the place
        ("Argentina", {"AR"}, {"CL"}),
        ("Colombia o Venezuela", {"CO", "VE"}, {"AR"}),
        ("any US state", {"US"}, {"AR"}),
        ("México", {"MX"}, set()),  # accents do not matter
        ("United States of America", {"US"}, set()),
        ("EEUU", {"US"}, set()),
        ("European Union", {"ES", "DE"}, {"GB", "AR"}),
        ("South America", {"AR", "BR"}, {"MX"}),
    ],
)
def test_places_resolve_to_the_countries_they_name(
    place: str, must_include: set[str], must_exclude: set[str]
):
    resolved = resolve_places([place])

    assert must_include <= resolved.countries
    assert not (must_exclude & resolved.countries)
    assert (resolved.ambiguous, resolved.unknown) == (False, False)


def test_several_places_are_added_together():
    assert resolve_places(["Chile", "Peru"]).countries == {"CL", "PE"}


@pytest.mark.parametrize(
    "place", ["Worldwide", "Global", "Anywhere", "Anywhere in the world", "Desde cualquier lugar"]
)
def test_words_that_open_the_job_to_everyone_are_worldwide(place: str):
    resolved = resolve_places([place])

    assert resolved.worldwide is True
    assert (resolved.ambiguous, resolved.unknown) == (False, False)
    assert resolved.countries == frozenset()


@pytest.mark.parametrize("term", ["Americas", "EMEA", "APAC", "Remote"])
def test_terms_that_name_no_definite_set_are_ambiguous(term: str):
    resolved = resolve_places([term])

    assert resolved.ambiguous is True
    assert resolved.countries == frozenset()


@pytest.mark.parametrize("place", ["Narnia", "Southern Cone", "Argentina or Narnia", "not US", ""])
def test_a_place_the_table_cannot_read_is_unknown_never_guessed(place: str):
    assert resolve_places([place]).unknown is True


def test_a_known_place_next_to_an_unknown_one_keeps_what_it_knows_and_flags_the_rest():
    resolved = resolve_places(["Chile", "Narnia"])

    assert resolved.countries == {"CL"}
    assert resolved.unknown is True


def test_no_places_at_all_resolves_to_nothing_and_the_rules_decide():
    resolved = resolve_places([])

    assert resolved.countries == frozenset()
    assert (resolved.worldwide, resolved.ambiguous, resolved.unknown) == (False, False, False)


def test_short_names_only_count_when_they_are_the_whole_text():
    assert resolve_places(["US"]).countries == {"US"}
    assert resolve_places(["join us in Chile"]).countries == {"CL"}  # "us" is not the country here


def test_the_data_is_consistent():
    """Every code is two capital letters and no spelling points to two different countries."""
    seen: dict[str, str] = {}
    for iso, spellings in COUNTRIES.items():
        assert len(iso) == 2 and iso.isupper()
        for spelling in spellings:
            owner = seen.setdefault(spelling.lower(), iso)
            assert owner == iso, f"{spelling!r} belongs to both {owner} and {iso}"
    for region, members in REGIONS.items():
        assert all(len(code) == 2 and code.isupper() for code in members), region


def test_a_spanish_quantifier_next_to_a_known_country_is_understood():
    resolved = resolve_places(["cualquier estado de USA"])

    assert resolved.countries == {"US"}
    assert resolved.unknown is False


def test_the_same_quantifier_alone_still_means_anywhere():
    assert resolve_places(["Cualquier pa\u00eds"]).worldwide is True


def test_a_spanish_exclusion_is_still_unreadable_even_with_the_quantifier():
    assert resolve_places(["cualquier pa\u00eds excepto Chile"]).unknown is True


@pytest.mark.parametrize(
    "text",
    [
        "Presencialidad hasta 2 d\u00edas por semana en oficinas de LATAM",
        "We hire across Latin America",
        "Trabajo 100% remoto desde Argentina",
        "Puedes trabajar desde cualquier lugar",
        "Open to the Americas",
    ],
)
def test_prose_that_may_include_the_users_country_is_noticed(text: str):
    assert mentions_area(text, "AR") is True


@pytest.mark.parametrize(
    "text",
    [
        "Modalidad h\u00edbrida, 3 d\u00edas en la oficina de Las Condes, Santiago",
        "We are a global company with offices in Santiago",  # "global" alone says nothing
    ],
)
def test_prose_that_names_only_other_places_is_not_a_match(text: str):
    assert mentions_area(text, "AR") is False


def test_a_short_name_that_is_also_a_word_does_not_count_as_the_country():
    assert mentions_area("Join us in Chile", "US") is False  # "us" is a pronoun here
    assert mentions_area("Remote from the USA", "US") is True
