"""Turn the places a posting names ("Latin America", "Colombia o Venezuela") into countries.

Shared by eligibility (places the model extracted) and the search prefilter (places a source
declares), so it lives in `core/`.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache

from src.config.data.locations import (
    AMBIGUOUS_TERMS,
    COUNTRIES,
    OPEN_PLACE_PHRASES,
    REGION_NAMES,
    REGIONS,
    WORLDWIDE_WORDS,
)
from src.core.text import fold

# Short names that are also ordinary words: accepted only when, ignoring filler words, they
# are all that the text says ("any US state" yes, "join us in Chile" no).
_EXACT_ONLY = {"us", "uk", "ue", "eu"}
# Words that may surround a place without adding or removing any place.
_FILLER = set(
    "or and o y e any of in within the a an state states estado estados resident residents "
    "residentes only solo solamente remote remoto based countries country paises pais region "
    "residence residencia en de del la el los las from desde to live living vivir located "
    "ubicado".split()
)
# Spanish "any", ignored only next to a country it quantifies ("cualquier estado de USA"). Not a
# filler everywhere: alone it means "anywhere" (WORLDWIDE_WORDS), which must keep working.
_QUANTIFIERS = {"cualquier", "cualquiera"}
# A place with one of these words is an exclusion ("not US"), which this table cannot read.
_NEGATIONS = {"not", "except", "excluding", "excepto", "sin", "no", "outside", "fuera"}


def _build_names() -> list[tuple[str, frozenset[str]]]:
    names: dict[str, frozenset[str]] = {}
    for iso, spellings in COUNTRIES.items():
        for spelling in spellings:
            names[fold(spelling)] = frozenset({iso})
    for region, spellings in REGION_NAMES.items():
        for spelling in spellings:
            names[fold(spelling)] = REGIONS[region]
    # Longest first, so "united states" is taken whole before "us" could match inside it.
    return sorted(names.items(), key=lambda item: -len(item[0]))


_NAMES = _build_names()
_AMBIGUOUS = {fold(term) for term in AMBIGUOUS_TERMS}
_WORLDWIDE = {fold(word) for word in WORLDWIDE_WORDS}


@dataclass(frozen=True)
class PlaceResolution:
    countries: frozenset[str] = frozenset()  # every country the places clearly include
    worldwide: bool = False  # some place says "anywhere" / "worldwide"
    ambiguous: bool = False  # some place names no definite set ("Americas")
    unknown: bool = False  # some place is not in the table, or is an exclusion
    names: list[str] = field(default_factory=list)  # the places as written, for messages


def _resolve_one(place: str) -> tuple[frozenset[str], bool, bool, bool]:
    """Returns (countries, worldwide, ambiguous, unknown) for one place as written."""
    text = fold(place)
    if _NEGATIONS & set(text.split()):
        return frozenset(), False, False, True
    words = set(text.split()) - _FILLER
    if words and words <= _WORLDWIDE:
        return frozenset(), True, False, False
    if text in _AMBIGUOUS:
        return frozenset(), False, True, False

    countries: set[str] = set()
    for name, members in _NAMES:
        if name in _EXACT_ONLY:
            if set(text.split()) - _FILLER == {name}:
                countries |= members
                text = ""
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])"
        if re.search(pattern, text):
            countries |= members
            text = re.sub(pattern, " ", text)
    leftover = set(text.split()) - _FILLER - (_QUANTIFIERS if countries else set())
    # Words we do not understand next to a known place may name another place: do not guess.
    return frozenset(countries), False, False, bool(leftover) or not countries


def resolve_places(places: list[str]) -> PlaceResolution:
    countries: set[str] = set()
    worldwide = ambiguous = unknown = False
    for place in places:
        found, is_worldwide, is_ambiguous, is_unknown = _resolve_one(place)
        countries |= found
        worldwide |= is_worldwide
        ambiguous |= is_ambiguous
        unknown |= is_unknown
    return PlaceResolution(frozenset(countries), worldwide, ambiguous, unknown, list(places))


@lru_cache
def _area_pattern(country: str) -> re.Pattern[str]:
    names = [n for n in COUNTRIES.get(country, ()) if fold(n) not in _EXACT_ONLY]
    names += [
        n
        for region, spellings in REGION_NAMES.items()
        if country in REGIONS[region]
        for n in spellings
    ]
    names += list(OPEN_PLACE_PHRASES)
    folded = sorted({fold(n) for n in names}, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(" + "|".join(map(re.escape, folded)) + r")(?![a-z0-9])")


def mentions_area(text: str, country: str) -> bool:
    """Does free text name the country, a region that includes it, or "anywhere"?

    A loose scan of prose, used only to keep a job for a closer look: a false "yes" costs one
    LLM call, a false "no" could cost a valid job, so it errs towards "yes". Short names that are
    also words ("us") are left out, or every English posting would match.
    """
    return bool(_area_pattern(country).search(fold(text)))
