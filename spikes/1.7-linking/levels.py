"""Level rules (system.md §11.4): pure functions, no LLM, no I/O.

Run the table tests:  uv run python spikes/1.7-linking/levels.py
"""

from datetime import date

from model import TODAY, Evidence, LevelResult, Link, Requirement

DAYS_PER_YEAR = 365.25
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
EDUCATION_ORDER = ["secondary", "tertiary", "bachelor", "master", "doctorate"]
SMALL_GAP = 0.5  # missing up to 50 % of the requested years -> "small" gap


# --- Years: union of date intervals ---------------------------------------------------------------


def union_years(items: list[Evidence]) -> float:
    """Years covered by the dated items, counting overlapping time once.

    Sort by start, then sweep: an interval that starts before the current one ends extends it,
    otherwise it opens a new block. Gaps between blocks are not counted.
    """
    spans = sorted(p for e in items for p in e.periods)
    total_days, block_start, block_end = 0, None, None
    for start, end in spans:
        if block_end is None or start > block_end:  # a gap: close the previous block
            if block_end is not None:
                total_days += (block_end - block_start).days
            block_start, block_end = start, end
        else:  # overlap or touching: extend
            block_end = max(block_end, end)
    if block_end is not None:
        total_days += (block_end - block_start).days
    return total_days / DAYS_PER_YEAR


def period(start: str, end: str | None) -> tuple[date, date]:
    """'YYYY-MM' strings -> (first day of start month, first day after the last month worked)."""
    y, m = map(int, start.split("-"))
    if end is None:
        return date(y, m, 1), TODAY
    ey, em = map(int, end.split("-"))
    return date(y, m, 1), date(ey + (em == 12), em % 12 + 1, 1)


def gap_size(have: float, need: float) -> str:
    return "small" if (need - have) / need <= SMALL_GAP else "large"


# --- skill / experience / credential: links decide, code computes ---------------------------------


def level_from_links(req: Requirement, links: list[Link], evidence: dict[str, Evidence]) -> LevelResult:
    """The §11.4 table. Unknown evidence IDs must be dropped before calling this."""
    if not links:
        return LevelResult("missing", reason="no_links")

    strong = [evidence[l.evidence_id] for l in links if l.relation in ("direct", "same", "equivalent")]
    if not strong:  # related-only is an argument for the user, not coverage
        return LevelResult("missing", reason="related_argument")

    detailed = [e for e in strong if e.strength == "detailed"]
    if detailed:
        if req.min_years is None:
            return LevelResult("met", reason="detailed_no_years_requested")
        years = union_years(detailed)
        if years >= req.min_years:
            return LevelResult("met", years=years, reason="years_enough")
        return LevelResult("partial", years=years, gap_size=gap_size(years, req.min_years), reason="years_short")

    if any(e.strength == "mention" for e in strong):
        if req.min_years is not None:
            return LevelResult("partial", reason="mention_without_detail")
        return LevelResult("met", reason="mention_no_years_requested")

    # only weak evidence: the CV itself says it is basic or vague
    return LevelResult("partial", reason="weak_mention")


LEVEL_ORDER = {"missing": 0, "partial": 1, "met": 2}


def level_from_parts(
    req: Requirement, parts: list[list[Link]], combinator: str, evidence: dict[str, Evidence]
) -> LevelResult:
    """Compound requirements: a level per part with the same rules, then combine in code.

    all ("A and B"): met only if every part is met; missing if no part has any evidence; else partial.
    any ("A or B"):  the best part wins.
    The LLM only splits the requirement and links evidence per part; it never judges the whole.
    """
    if not parts:
        return LevelResult("missing", reason="no_parts")
    per_part = [level_from_links(req, links, evidence) for links in parts]
    if combinator == "any":
        return max(per_part, key=lambda r: LEVEL_ORDER[r.level])
    if all(r.level == "met" for r in per_part):
        return LevelResult("met", reason="all_parts_met")
    if all(r.level == "missing" for r in per_part):
        return LevelResult("missing", reason="no_part_covered")
    return LevelResult("partial", reason="some_parts_not_met")


# --- code-only types ------------------------------------------------------------------------------


def level_language(req: Requirement, have: Evidence | None) -> LevelResult:
    """Compare CEFR levels. Self-assessed levels are noted in the reason, not hidden."""
    if have is None:
        return LevelResult("missing", reason="language_absent")
    got = "C2" if have.cefr == "native" else have.cefr
    suffix = "" if have.level_source != "self_assessed" else "+self_assessed"
    diff = CEFR_ORDER.index(req.cefr) - CEFR_ORDER.index(got)
    if diff <= 0:
        return LevelResult("met", reason="cefr_enough" + suffix)
    return LevelResult("partial", gap_size="small" if diff == 1 else "large", reason="cefr_lower" + suffix)


def level_education(req: Requirement, have_rank: str, experience_years: float = 0.0) -> LevelResult:
    """Ordinal scale; 'or equivalent experience' counts as met with enough years."""
    if EDUCATION_ORDER.index(have_rank) >= EDUCATION_ORDER.index(req.education_rank):
        return LevelResult("met", reason="education_enough")
    if req.equivalent_experience_ok and req.min_years is not None and experience_years >= req.min_years:
        return LevelResult("met", years=experience_years, reason="equivalent_experience")
    return LevelResult("partial", gap_size="small", reason="education_lower")


def is_scored(req: Requirement) -> bool:
    """soft requirements are not assessable and conditions are shown apart: neither gets a level."""
    return req.type not in ("soft", "condition")


# --- table tests ----------------------------------------------------------------------------------


def _ev(id: str, start: str, end: str | None, strength: str = "detailed") -> Evidence:
    """Build an evidence item from 'YYYY-MM' strings; end is the last month worked (None = ongoing)."""
    return Evidence(id=id, kind="experience", name=id, strength=strength, periods=(period(start, end),))


def _req(**kw) -> Requirement:
    base = dict(key="t", job="t", type="skill", required="required", text="t")
    return Requirement(**{**base, **kw})


def run_tests() -> None:
    nimbus = _ev("E1", "2022-03", None)  # ongoing
    pampa = _ev("E2", "2019-06", "2022-02")
    freelance = _ev("E3", "2018-01", "2020-12")
    ev = {e.id: e for e in (nimbus, pampa, freelance)}

    # 1. Union, not sum: the three jobs overlap and touch, so the union is one continuous block.
    all_three = union_years([nimbus, pampa, freelance])
    summed = sum(union_years([e]) for e in (nimbus, pampa, freelance))
    expected = (TODAY - date(2018, 1, 1)).days / DAYS_PER_YEAR
    assert abs(all_three - expected) < 0.01, (all_three, expected)
    assert summed - all_three > 1.5, "overlap must not be double counted"

    # 2. A gap is not counted: 2015-2017 and 2019-2021 = 6 years, not 7.
    a, b = _ev("A", "2015-01", "2017-12"), _ev("B", "2019-01", "2021-12")
    assert abs(union_years([a, b]) - 6.0) < 0.01

    # 3. Level table (system.md §11.4)
    def lvl(min_years, rels, strength="detailed", items=None):
        items = items or [_ev("X", "2019-06", "2022-02", strength)]
        e = {i.id: i for i in items}
        links = [Link(i.id, r) for i, r in zip(items, rels)]
        return level_from_links(_req(min_years=min_years), links, e)

    assert lvl(None, []).level == "missing"
    assert lvl(None, ["related"]).level == "missing"  # related is an argument, not coverage
    assert lvl(None, ["same"]).level == "met"
    assert lvl(2, ["same"]).level == "met"  # 2y9m >= 2
    r = lvl(4, ["equivalent"])  # 2.7 of 4: short by 32 % -> small
    assert (r.level, r.gap_size) == ("partial", "small"), r
    r = lvl(7, ["same"])  # 2.7 of 7: short by 61 % -> large
    assert (r.level, r.gap_size) == ("partial", "large"), r
    assert lvl(4, ["same"], strength="mention").level == "partial"  # years asked, only a mention
    assert lvl(None, ["same"], strength="mention").level == "met"  # no years asked
    # two strong links: years are the union of both jobs (2.7 + 4.7 = 7.4y, no overlap here)
    assert lvl(4, ["same", "same"], items=[pampa, nimbus]).level == "met"
    # `related` adds no years: only Pampa counts (2.7y < 4) even though Nimbus is also linked
    r = lvl(4, ["same", "related"], items=[pampa, nimbus])
    assert (r.level, r.gap_size) == ("partial", "small"), r
    assert lvl(None, ["related", "related"], items=[pampa, nimbus]).level == "missing"
    assert lvl(2, ["direct"]).level == "met"  # `direct` is the v4 name for same/equivalent

    # 4. Languages
    spanish = Evidence("L1", "language", "Spanish", "detailed", cefr="native", level_source="native")
    english = Evidence("L2", "language", "English", "detailed", cefr="C1", level_source="certificate")
    portuguese = Evidence("L3", "language", "Portuguese", "detailed", cefr="B1", level_source="self_assessed")
    assert level_language(_req(type="language", cefr="B2"), english).level == "met"
    assert level_language(_req(type="language", cefr="C2"), english) == LevelResult("partial", gap_size="small", reason="cefr_lower")
    r = level_language(_req(type="language", cefr="C1"), portuguese)
    assert (r.level, r.gap_size, r.reason) == ("partial", "large", "cefr_lower+self_assessed"), r
    assert level_language(_req(type="language", cefr="C2"), spanish).level == "met"
    assert level_language(_req(type="language", cefr="B1"), None).level == "missing"

    # 5. Education
    assert level_education(_req(education_rank="bachelor"), "bachelor").level == "met"
    assert level_education(_req(education_rank="master"), "bachelor").level == "partial"
    r = level_education(_req(education_rank="master", equivalent_experience_ok=True, min_years=5), "bachelor", 8.9)
    assert r.reason == "equivalent_experience"

    # 6. soft / condition are never scored
    assert not is_scored(_req(type="soft")) and not is_scored(_req(type="condition"))
    assert is_scored(_req(type="skill")) and is_scored(_req(type="language"))

    # 7. weak evidence (the CV says "basic", "coursework", "familiar with") is never enough for met
    weak = Evidence("W", "skill", "CI/CD", "weak")
    assert level_from_links(_req(), [Link("W", "same")], {"W": weak}) == LevelResult("partial", reason="weak_mention")

    # 8. parts: a level per part, combined in code
    ev7 = {**ev, "W": weak}
    met_part, weak_part, none_part = [Link("E1", "same")], [Link("W", "same")], []
    assert level_from_parts(_req(), [met_part, met_part], "all", ev7).level == "met"
    assert level_from_parts(_req(), [met_part, none_part], "all", ev7).level == "partial"
    assert level_from_parts(_req(), [none_part, none_part], "all", ev7).level == "missing"
    # "Python and AWS": AWS detailed, Python only coursework -> partial, NOT met
    assert level_from_parts(_req(), [met_part, weak_part], "all", ev7).level == "partial"
    assert level_from_parts(_req(), [met_part, none_part], "any", ev7).level == "met"
    assert level_from_parts(_req(), [], "all", ev7).level == "missing"
    # years apply to each part: 4y asked, Pampa (2.7y) covers part 2 -> partial
    assert level_from_parts(_req(min_years=4), [[Link("E1", "same")], [Link("E2", "same")]], "all", ev7).level == "partial"

    print("levels.py: all table tests passed")


if __name__ == "__main__":
    run_tests()
