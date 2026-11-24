"""Hand labels for spike 1.7, written BEFORE any linking run (go/no-go discipline).

Reference profile: Martina Sosa (evidence.py). For each requirement:
- strong:  evidence IDs that SHOULD be linked as same/equivalent
- related: evidence IDs that SHOULD be linked only as related (cover part of the requirement)
- level:   the level a careful human would give (None = never scored)
- doubt:   non-empty = borderline, reviewed by the user; reported apart, never hidden
- also_ok: other levels accepted for a borderline label (never `met` when the label is lower)

The level is judged by a person, NOT computed from the links: where the §11.4 rules and the
human level disagree, `python labels.py` lists it as a rule conflict.
"""

from evidence import BY_ID, EDUCATION_RANK, LANGUAGES
from levels import is_scored, level_education, level_from_links, level_language, union_years
from model import Link
from labels_holdout import LABELS_HOLDOUT
from requirements import BY_KEY, HOLDOUT, LLM_TYPES

JOBS = ["E1", "E2", "E3", "E4"]  # the four jobs: 10.7 years as a developer


def L(level, strong=(), related=(), doubt="", also_ok=()):
    return dict(level=level, strong=list(strong), related=list(related), doubt=doubt, also_ok=list(also_ok))


LABELS_MAIN: dict[str, dict] = {
    # --- 01 Full-Stack Node.js / React ---
    "p01-r01": L("met"),  # education, code: bachelor >= bachelor
    "p01-r02": L("met"),  # Spanish native >= B2
    "p01-r03": L("met", strong=JOBS),  # 10.7y >= 4
    "p01-r04": L("partial", strong=["E9", "E17", "E5"],
                 doubt="RULE CONFLICT: 'Advanced' cannot be assessed from the CV and Node.js is only a backend-for-frontend "
                       "(2.7y); the links are right but the rules give `met` (they cannot see the qualifier)"),
    "p01-r05": L("partial", related=["E10"]),  # relational yes, NoSQL absent: PostgreSQL covers half
    "p01-r06": L("missing"),
    "p01-r07": L(None),  # soft
    # --- 04 Senior Full-Stack, 5+ years ---
    "p04-r01": L("met", strong=JOBS),  # 10.7y >= 5
    "p04-r02": L("met", strong=["E10"]),  # PostgreSQL = SQL
    "p04-r03": L("met", strong=["E13"], also_ok=["partial"],
                 doubt="POST-RESULT RELABEL (v4 run): was `missing` by the mechanical effect of the related definition. "
                       "Consuming GraphQL APIs is a defensible `met`; the CV does not say the APIs were third-party"),
    "p04-r04": L("met"),  # English C1 >= C1
    "p04-r05": L("missing"),  # nice to have
    "p04-r06": L(None),  # condition
    # --- 09 Fractional Full-Stack, TypeScript / Next.js / Supabase ---
    "p09-r01": L("met", strong=["E6"]),  # TypeScript 4.7y >= 2
    "p09-r02": L("met", strong=["E5", "E7"],
                 doubt="React and Next.js are there; App Router, React 18 and server/client boundaries are not written in the CV"),
    "p09-r03": L("partial", related=["E10"]),  # Postgres yes, Supabase / RLS / Auth absent
    "p09-r04": L("missing", related=["E14"],
                 doubt="Deploys on AWS S3/CloudFront, not on Vercel: related platform, same activity"),
    "p09-r05": L("met", strong=["E11"]),
    "p09-r06": L("missing"),
    "p09-r07": L("met"),  # English C1
    "p09-r08": L("met", strong=["E12"]),  # nice to have; Playwright
    # --- 11 Contentful lead role ---
    "p11-r01": L("missing"),
    "p11-r02": L("missing", also_ok=["partial"], doubt="She led a code migration (CRA to Next.js); a model may link it as 'related' to content migration"),
    "p11-r03": L("met", strong=["E19", "E3"],
                 doubt="Led technical decisions (E19) and worked for clients as a freelancer (E3); no title of lead"),
    "p11-r04": L("met"),  # English C1
    "p11-r05": L("met", strong=["E6", "E17"]),  # nice to have; JS/TS
    "p11-r06": L("missing", related=["E13"]),  # nice to have; GraphQL yes, Contentful no
    # --- 14 Technical Lead (Python, AWS, API) ---
    "p14-r01": L("met", strong=JOBS),  # 10.7y >= 7
    "p14-r02": L("met", strong=["E19"],
                 doubt="Led a complex migration project and mentored 3 juniors, but never held a team-lead role"),
    "p14-r03": L("partial", related=["E14", "E23"]),  # Python = coursework, AWS = S3/CloudFront, no distributed systems
    "p14-r04": L("partial", related=["E9", "E13"]),  # builds and consumes APIs; no microservices or event-driven
    "p14-r05": L("partial", strong=["E27"],
                 doubt="RULE CONFLICT: only a vague 'familiar with CI/CD' (mention). §11.4 gives `met` for a mention with no years asked"),
    "p14-r06": L("met", strong=["E5", "E6"]),
    "p14-r07": L("missing"),
    "p14-r08": L(None),  # soft
}


LABELS = LABELS_HOLDOUT if HOLDOUT else LABELS_MAIN

# Requirements excluded from the thresholds because the RULES cannot see the qualifier (declared before any run).
# v4: p14-r05 ("familiar with CI/CD") left this list in v3 (weak evidence); p01-r04 ("advanced") remains.
# The held-out set declares none: any rule gap that shows up there is counted, not excluded.
CONFLICTS = [] if HOLDOUT else ["p01-r04"]

# v4 decision, before any run: `related` no longer gives partial, so three labels that were partial only
# through a related link are now `missing` (p04-r03, p09-r04, p11-r06). Their strong/related lists stay for reading.


def rule_level(key: str):
    """Level the §11.4 rules compute from the LABELLED links (what a perfect linker would get)."""
    r, lab = BY_KEY[key], LABELS[key]
    if not is_scored(r):
        return None
    if r.type == "education":
        return level_education(r, EDUCATION_RANK).level
    if r.type == "language":
        return level_language(r, LANGUAGES[r.language]).level
    links = [Link(i, "same") for i in lab["strong"]] + [Link(i, "related") for i in lab["related"]]
    return level_from_links(r, links, BY_ID).level


if __name__ == "__main__":
    assert set(LABELS) == set(BY_KEY), set(LABELS) ^ set(BY_KEY)
    for k, lab in LABELS.items():
        for i in lab["strong"] + lab["related"]:
            assert i in BY_ID, (k, i)
    conflicts = [k for k, lab in LABELS.items() if rule_level(k) != lab["level"]]
    print(f"{len(LABELS)} labels | scored: {sum(1 for l in LABELS.values() if l['level'])} "
          f"| to the LLM: {sum(1 for r in BY_KEY.values() if r.type in LLM_TYPES)} | doubtful: "
          f"{sum(1 for l in LABELS.values() if l['doubt'])}")
    print("rule conflicts (label level != level the rules compute from the labelled links):")
    for k in conflicts:
        print(f"  {k}: label={LABELS[k]['level']} rules={rule_level(k)} | {BY_KEY[k].text}")
    print(f"label distribution: { {lv: sum(1 for l in LABELS.values() if l['level'] == lv) for lv in ('met', 'partial', 'missing')} }")
    print(f"years check: jobs union = {union_years([BY_ID[i] for i in JOBS]):.1f}y")
