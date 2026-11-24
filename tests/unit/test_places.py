import pytest

from src.app.eligibility.places import resolve_places
from src.config.data.locations import COUNTRIES, REGIONS


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


@pytest.mark.parametrize("term", ["Worldwide", "Global", "Americas", "EMEA", "Anywhere"])
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


def test_no_places_at_all_is_unknown():
    assert resolve_places([]).unknown is True


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
