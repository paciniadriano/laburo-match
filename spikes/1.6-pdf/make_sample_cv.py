"""Generate the fictional sample CV used by tests, evals and demo mode.

Run (reportlab is only needed here, so it is not a project dependency):
    uv run --no-project --with reportlab python make_sample_cv.py

The content is designed to exercise profile rules, not to look impressive:
- overlapping experiences (years must be a union of intervals),
- a certified and a self-assessed language level (CEFR mapping),
- skills listed without supporting experience (weak evidence),
- vague mentions that build_profile should ask about,
- date of birth and national ID that must NOT reach the profile.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUTPUT = Path(__file__).resolve().parents[2] / "data" / "samples" / "sample_cv.pdf"

HEADER = {
    "name": "Martina Sosa",
    "title": "Senior Frontend Engineer",
    "contact": "Rosario, Santa Fe, Argentina · martina.sosa@example.com · +54 341 555-0100",
    "personal": "Date of birth: 14/03/1993 · DNI 12.345.678 · Citizenship: Argentine and Italian",
}

SUMMARY = (
    "Frontend engineer with 8+ years building web products, mostly with React and "
    "TypeScript. Experience with cloud platforms and familiar with CI/CD. "
    "Looking for remote roles in product companies."
)

# (title, company, dates, bullets). Freelance overlaps Pampa Fintech on purpose.
EXPERIENCES = [
    (
        "Senior Frontend Engineer",
        "Nimbus Logistics (remote)",
        "Mar 2022 – Present",
        [
            "Led the migration of the customer portal from Create React App to Next.js, "
            "cutting the initial load time by 40%.",
            "Built a shared component library in React and TypeScript used by 4 teams.",
            "Introduced Playwright end-to-end tests and raised unit test coverage with Jest.",
            "Mentored 3 junior developers; ran weekly code reviews.",
            "Consumed GraphQL APIs with Apollo Client.",
        ],
    ),
    (
        "Frontend Developer",
        "Pampa Fintech",
        "Jun 2019 – Feb 2022",
        [
            "Developed the onboarding and payments flows in React and Redux.",
            "Maintained a Node.js (Express) backend-for-frontend with a PostgreSQL database.",
            "Deployed static assets to AWS S3 and CloudFront.",
        ],
    ),
    (
        "Freelance Web Developer",
        "Self-employed",
        "Jan 2018 – Dec 2020",
        [
            "Built websites for small businesses with WordPress and PHP.",
            "Developed two single-page apps with Vue.js.",
        ],
    ),
    (
        "Junior Developer",
        "Estudio Delta",
        "Mar 2016 – May 2019",
        [
            "Built internal tools with JavaScript, jQuery, HTML and CSS.",
            "Fixed bugs in an ASP.NET MVC application.",
        ],
    ),
]

EDUCATION = [
    "Systems Engineering (Ingeniería en Sistemas de Información), "
    "Universidad Tecnológica Nacional, Rosario · 2011 – 2017",
]

SKILLS = [
    "Languages: TypeScript, JavaScript, HTML, CSS, PHP, Python (coursework)",
    "Frontend: React, Next.js, Redux, Vue.js, Apollo Client, Tailwind CSS",
    "Backend: Node.js, Express, PostgreSQL",
    "Testing: Jest, Playwright, React Testing Library",
    "Tools: Git, Docker (basic), Figma",
]

LANGUAGES = [
    "Spanish: native",
    "English: C1 (Cambridge C1 Advanced, 2018)",
    "Portuguese: intermediate",
]


def build_story(styles=None) -> list:
    """Turn the CV data into reportlab flowables, in reading order (single column).

    `styles` lets other scripts reuse the same layout with a different font.
    """
    styles = styles or getSampleStyleSheet()
    h1, h2, body = styles["Title"], styles["Heading2"], styles["BodyText"]
    story = [
        Paragraph(HEADER["name"], h1),
        Paragraph(HEADER["title"], body),
        Paragraph(HEADER["contact"], body),
        Paragraph(HEADER["personal"], body),
        Spacer(1, 0.4 * cm),
        Paragraph("Summary", h2),
        Paragraph(SUMMARY, body),
        Paragraph("Experience", h2),
    ]
    for title, company, dates, bullets in EXPERIENCES:
        story.append(Paragraph(f"<b>{title}</b> · {company} · {dates}", body))
        # "-" instead of "•": the built-in Helvetica has no clean Unicode mapping for
        # the bullet and pypdf extracts it as "\x7f". This file is the easy baseline.
        story.extend(Paragraph(f"- {bullet}", body) for bullet in bullets)
        story.append(Spacer(1, 0.2 * cm))
    for heading, lines in (("Education", EDUCATION), ("Skills", SKILLS), ("Languages", LANGUAGES)):
        story.append(Paragraph(heading, h2))
        story.extend(Paragraph(line, body) for line in lines)
    return story


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # invariant=True drops timestamps and random IDs, so the same input gives the
    # same bytes (a stable sha256, no noise in git diffs).
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        title="Sample CV (fictional)",
        author="laburo-match",
        invariant=True,
    )
    doc.build(build_story())
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
