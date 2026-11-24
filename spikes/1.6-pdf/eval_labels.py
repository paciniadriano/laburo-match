"""Hand labels for spike 1.6: what each CV really says (written from the source data, not from LLM output)."""

from parse_set import HERE

SAMPLE_PDF = HERE.parents[1] / "data" / "samples" / "sample_cv.pdf"

NIMBUS = dict(
    title="Senior Frontend Engineer", company="Nimbus", start="Mar 2022", end="Present",
    bullets=["Led the migration", "Built a shared component library", "Introduced Playwright", "Mentored 3 junior"],
)
PAMPA = dict(
    title="Frontend Developer", company="Pampa", start="Jun 2019", end="Feb 2022",
    bullets=["Developed the onboarding", "Maintained a Node.js", "Deployed static assets"],
)
FREELANCE = dict(
    title="Freelance Web Developer", company="Self-employed", start="Jan 2018", end="Dec 2020",
    bullets=["Built websites for small businesses", "Developed two single-page apps"],
)
DELTA = dict(
    title="Junior Developer", company="Estudio Delta", start="Mar 2016", end="May 2019",
    bullets=["Built internal tools", "Fixed bugs in an ASP.NET"],
)
# The sample CV has one more Nimbus bullet that the Canva copy does not.
NIMBUS_FULL = {**NIMBUS, "bullets": NIMBUS["bullets"] + ["Consumed GraphQL"]}

SAMPLE_SKILLS = [
    "TypeScript", "JavaScript", "HTML", "CSS", "PHP", "Python", "React", "Next.js", "Redux", "Vue.js",
    "Apollo Client", "Tailwind CSS", "Node.js", "Express", "PostgreSQL", "Jest", "Playwright",
    "React Testing Library", "Git", "Docker", "Figma",
]
CANVA_SKILLS = [
    "TypeScript", "JavaScript", "React", "Next.js", "Redux", "Vue.js", "Node.js", "Express",
    "PostgreSQL", "Jest", "Playwright", "Git", "Docker", "Python",
]

# Language checks: the LLM copies what is written; certificate presence decides certified vs self-assessed.
LANGUAGES = {
    "spanish": lambda l: "native" in l.stated_level.casefold() or "nativ" in l.stated_level.casefold(),
    "english": lambda l: "c1" in l.stated_level.casefold() and l.certificate.strip() != "",
    "portuguese": lambda l: "intermediate" in l.stated_level.casefold() and l.certificate.strip() == "",
}

COMMON = dict(
    languages=LANGUAGES, citizenships=["argentin", "italian"], vague=["cloud platforms", "ci/cd"],
)

# The labels of the author's real CV are kept local (personal data); only the public sets are archived.

LABELS = {
    "sample_pypdf": dict(path=SAMPLE_PDF, engine="pypdf", skills=SAMPLE_SKILLS,
                         experiences=[NIMBUS_FULL, PAMPA, FREELANCE, DELTA], **COMMON),
    "two_column_pypdf": dict(path=HERE / "hard" / "two_column.pdf", engine="pypdf", skills=SAMPLE_SKILLS,
                             experiences=[NIMBUS_FULL, PAMPA, FREELANCE, DELTA], **COMMON),
    "canva_pypdf": dict(path=HERE / "real" / "canva_cv.pdf", engine="pypdf", skills=CANVA_SKILLS,
                        experiences=[NIMBUS, PAMPA, FREELANCE], **COMMON),
    "canva_pdfminer": dict(path=HERE / "real" / "canva_cv.pdf", engine="pdfminer", skills=CANVA_SKILLS,
                           experiences=[NIMBUS, PAMPA, FREELANCE], **COMMON),
}
