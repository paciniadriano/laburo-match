"""Requirements of the 5 postings, cleaned by hand from the posting text (fixed input of the spike).

Texts are normalized to English; the wording stays close to the posting, including compound
requirements ("Postgres and Supabase") on purpose: real postings are written like that and
those are the ones that can produce a false `met`.
"""

import os

from model import Requirement
from requirements_holdout import REQUIREMENTS_HOLDOUT

ENGLISH = "English, advanced level"  # same text in three postings -> same requirement_key (dedupe)


def _r(job, n, type, required, text, **kw) -> Requirement:
    return Requirement(key=f"p{job}-r{n:02d}", job=job, type=type, required=required, text=text, **kw)


REQUIREMENTS_MAIN: list[Requirement] = [
    # --- 01 Full-Stack (Node.js / React), Spanish posting ---
    _r("01", 1, "education", "required", "University degree in Computer Science, Computer Engineering or a related field",
       education_rank="bachelor"),
    _r("01", 2, "language", "required", "Spanish (level not stated, B2 assumed)", language="spanish", cefr="B2"),
    _r("01", 3, "experience", "required", "Minimum 4 years of proven experience as a software developer", min_years=4),
    _r("01", 4, "skill", "required", "Advanced proficiency in Node.js, JavaScript and React"),
    _r("01", 5, "skill", "required", "Experience with both relational and NoSQL databases"),
    _r("01", 6, "skill", "required", "Use of data structures and algorithms to solve complex problems"),
    _r("01", 7, "soft", "required", "Excellent communication skills to share knowledge and guide the team"),
    # --- 04 Senior Full-Stack Engineer, 5+ years ---
    _r("04", 1, "experience", "required", "5+ years of professional software engineering experience", min_years=5),
    _r("04", 2, "skill", "required", "Strong knowledge of SQL"),
    _r("04", 3, "skill", "required", "Third-party API integrations"),
    _r("04", 4, "language", "required", ENGLISH, language="english", cefr="C1"),
    _r("04", 5, "skill", "nice_to_have", "WebRTC, SIP, telecommunications, networking, AI systems or ISP software"),
    _r("04", 6, "condition", "required", "At least five working hours of overlap with Pacific Time"),
    # --- 09 Fractional Full-Stack Engineer (TypeScript / Next.js / Supabase) ---
    _r("09", 1, "skill", "required", "Professional TypeScript experience", min_years=2),
    _r("09", 2, "skill", "required",
       "Strong React 18 and Next.js experience, including App Router, API routes and server/client component boundaries"),
    _r("09", 3, "skill", "required",
       "Working knowledge of Postgres and Supabase, including SQL, migrations, Row-Level Security, Auth and Storage"),
    _r("09", 4, "skill", "required", "Experience deploying and debugging applications on Vercel"),
    _r("09", 5, "skill", "required", "Writes and maintains unit and component tests"),
    _r("09", 6, "skill", "required", "Productive with AI coding tools such as Claude Code or Cursor"),
    _r("09", 7, "language", "required", ENGLISH, language="english", cefr="C1"),
    _r("09", 8, "skill", "nice_to_have", "Playwright or similar end-to-end testing"),
    # --- 11 "Front-end" Software Engineer (really a Contentful lead role) ---
    _r("11", 1, "skill", "required", "Contentful content modeling and space architecture"),
    _r("11", 2, "skill", "required", "Content migration planning and execution"),
    _r("11", 3, "experience", "required", "Leading technical decisions and working directly with clients"),
    _r("11", 4, "language", "required", ENGLISH, language="english", cefr="C1"),
    _r("11", 5, "skill", "nice_to_have", "JavaScript or TypeScript for writing migration scripts"),
    _r("11", 6, "skill", "nice_to_have", "Familiarity with Contentful GraphQL and Content Delivery APIs"),
    # --- 14 Technical Lead (Python, AWS, API), Spanish posting ---
    _r("14", 1, "experience", "required", "At least 7 years of software development experience", min_years=7),
    _r("14", 2, "experience", "required", "Proven ability to lead technology teams or complex projects"),
    _r("14", 3, "skill", "required", "Solid knowledge of Python and AWS, with experience in distributed architectures"),
    _r("14", 4, "skill", "required",
       "Experience developing and consuming APIs, working with microservices and event-driven patterns"),
    _r("14", 5, "skill", "required", "Experience with CI/CD and continuous delivery practices"),
    _r("14", 6, "skill", "required", "Practical knowledge of React and TypeScript"),
    _r("14", 7, "skill", "required", "Experience designing scalable and secure systems"),
    _r("14", 8, "soft", "required", "Mentoring ability, effective communication and a collaborative attitude"),
]

# SPIKE_SET=holdout switches the whole spike (split, link, evaluate) to the held-out postings 05 and 12.
HOLDOUT = os.environ.get("SPIKE_SET") == "holdout"
REQUIREMENTS: list[Requirement] = REQUIREMENTS_HOLDOUT if HOLDOUT else REQUIREMENTS_MAIN

BY_KEY: dict[str, Requirement] = {r.key: r for r in REQUIREMENTS}
LLM_TYPES = ("skill", "experience", "credential")  # everything else is resolved in code


def dedupe_key(r: Requirement) -> str:
    """requirement_key from system.md §11.4: normalized text + type + min_years."""
    return f"{' '.join(r.text.casefold().split())}|{r.type}|{r.min_years}"


def for_linking() -> list[Requirement]:
    """Unique requirements the LLM must link: deduplicated across the whole run."""
    seen: dict[str, Requirement] = {}
    for r in REQUIREMENTS:
        if r.type in LLM_TYPES:
            seen.setdefault(dedupe_key(r), r)
    return list(seen.values())


if __name__ == "__main__":
    from collections import Counter

    assert len(BY_KEY) == len(REQUIREMENTS), "duplicate requirement keys"
    print(f"{len(REQUIREMENTS)} requirements: {dict(Counter(r.type for r in REQUIREMENTS))}")
    print(f"unique keys overall: {len({dedupe_key(r) for r in REQUIREMENTS})} | sent to the LLM: {len(for_linking())}")
    print("by posting:", dict(Counter(r.job for r in REQUIREMENTS)))
