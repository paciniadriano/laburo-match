"""Evidence of the reference profile (Martina Sosa, data/samples/sample_cv.pdf), built by hand.

Built by hand on purpose: spike 1.5/1.6 already measured extraction; here only linking is under test.
Rules used to build it (same as the real pipeline will follow):
- `detailed` = the skill appears inside a job bullet, dated with the jobs where it is used.
- `mention`  = only listed in Skills / Summary, no dates. The qualifier written in the CV goes in `note`.
- `weak`     = a mention the CV itself qualifies as weak ("basic", "coursework", "familiar with", vague claims).
"""

from levels import period
from model import Evidence

NIMBUS = period("2022-03", None)
PAMPA = period("2019-06", "2022-02")
FREELANCE = period("2018-01", "2020-12")
DELTA = period("2016-03", "2019-05")


def _e(id, kind, name, strength="detailed", periods=(), note="", **kw) -> Evidence:
    return Evidence(id=id, kind=kind, name=name, strength=strength, periods=tuple(periods), note=note, **kw)


EVIDENCE: list[Evidence] = [
    # --- Jobs (kind experience) ---
    _e("E1", "experience", "Senior Frontend Engineer at Nimbus Logistics", periods=[NIMBUS],
       note="Mar 2022 - present; customer portal, shared component library used by 4 teams"),
    _e("E2", "experience", "Frontend Developer at Pampa Fintech", periods=[PAMPA],
       note="Jun 2019 - Feb 2022; onboarding and payments flows"),
    _e("E3", "experience", "Freelance Web Developer", periods=[FREELANCE],
       note="Jan 2018 - Dec 2020; websites for small businesses"),
    _e("E4", "experience", "Junior Developer at Estudio Delta", periods=[DELTA],
       note="Mar 2016 - May 2019; internal tools, bug fixes"),
    # --- Skills used in job bullets (detailed, dated by the jobs that use them) ---
    _e("E5", "skill", "React", periods=[NIMBUS, PAMPA], note="component library, portal, onboarding and payments flows"),
    _e("E6", "skill", "TypeScript", periods=[NIMBUS], note="used with React in the component library"),
    _e("E7", "skill", "Next.js", periods=[NIMBUS], note="led the migration from Create React App to Next.js, -40% initial load"),
    _e("E8", "skill", "Redux", periods=[PAMPA]),
    _e("E9", "skill", "Node.js (Express)", periods=[PAMPA], note="backend-for-frontend with PostgreSQL"),
    _e("E10", "skill", "PostgreSQL", periods=[PAMPA], note="database of the Node.js backend-for-frontend"),
    _e("E11", "skill", "Unit and component testing (Jest, React Testing Library)", periods=[NIMBUS],
       note="raised unit test coverage"),
    _e("E12", "skill", "Playwright end-to-end testing", periods=[NIMBUS]),
    _e("E13", "skill", "GraphQL APIs with Apollo Client", periods=[NIMBUS], note="consumed GraphQL APIs"),
    _e("E14", "skill", "AWS S3 and CloudFront", periods=[PAMPA], note="deployed static assets"),
    _e("E15", "skill", "Vue.js", periods=[FREELANCE], note="two single-page apps"),
    _e("E16", "skill", "WordPress and PHP", periods=[FREELANCE]),
    _e("E17", "skill", "JavaScript, jQuery, HTML and CSS", periods=[DELTA, FREELANCE]),
    _e("E18", "skill", "ASP.NET MVC", periods=[DELTA], note="bug fixes in an existing application"),
    _e("E19", "other", "Led the migration of the customer portal and made technical decisions", periods=[NIMBUS]),
    _e("E20", "other", "Mentored 3 junior developers and ran weekly code reviews", periods=[NIMBUS]),
    # --- Mentions (listed) and weak mentions (qualified as basic / vague by the CV), no dates ---
    _e("E21", "skill", "Git", "mention", note="listed under Tools"),
    _e("E22", "skill", "Docker", "weak", note="written as 'Docker (basic)'"),
    _e("E23", "skill", "Python", "weak", note="written as 'Python (coursework)'"),
    _e("E24", "skill", "Figma", "mention"),
    _e("E25", "skill", "Tailwind CSS", "mention"),
    _e("E26", "skill", "Cloud platforms", "weak", note="vague: 'Experience with cloud platforms' in the summary"),
    _e("E27", "skill", "CI/CD", "weak", note="vague: 'familiar with CI/CD' in the summary"),
    # --- Code-only evidence (never sent to the LLM) ---
    _e("E28", "education", "Systems Engineering, Universidad Tecnologica Nacional", periods=[period("2011-03", "2017-12")],
       note="bachelor"),
    _e("E29", "language", "Spanish", cefr="native", level_source="native"),
    _e("E30", "language", "English", note="Cambridge C1 Advanced, 2018", cefr="C1", level_source="certificate"),
    _e("E31", "language", "Portuguese", note="written as 'intermediate'", cefr="B1", level_source="self_assessed"),
]

BY_ID: dict[str, Evidence] = {e.id: e for e in EVIDENCE}
LANGUAGES: dict[str, Evidence] = {e.name.casefold(): e for e in EVIDENCE if e.kind == "language"}
EDUCATION_RANK = "bachelor"  # E28


def llm_visible() -> list[Evidence]:
    """Evidence the linking prompt may reference: language and education are compared in code."""
    return [e for e in EVIDENCE if e.kind not in ("language", "education")]


if __name__ == "__main__":
    from levels import union_years

    assert len(BY_ID) == len(EVIDENCE), "duplicate evidence ids"
    print(f"{len(EVIDENCE)} items, {len(llm_visible())} visible to the LLM")
    for id in ("E5", "E9", "E6"):
        print(f"  {id} {BY_ID[id].name}: {union_years([BY_ID[id]]):.2f} years")
    print(f"  all jobs (E1-E4) union: {union_years([BY_ID[i] for i in ('E1', 'E2', 'E3', 'E4')]):.2f} years")
