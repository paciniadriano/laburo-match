"""Held-out requirements (postings 05 and 12): never seen while tuning v1-v4. Written before any run.

Same cleaning rules as requirements.py: normalized English, wording close to the posting, compound
requirements kept compound. Soft statements and the location condition are typed as such.
"""

from model import Requirement

ENGLISH = "English, advanced level"  # same text as requirements.py -> same requirement_key


def _r(job, n, type, required, text, **kw) -> Requirement:
    return Requirement(key=f"p{job}-r{n:02d}", job=job, type=type, required=required, text=text, **kw)


REQUIREMENTS_HOLDOUT: list[Requirement] = [
    # --- 05 Senior Full-Stack (Go + Next.js + React Native) ---
    _r("05", 1, "experience", "required", "5+ years of full-stack experience", min_years=5),
    _r("05", 2, "skill", "required",
       "Strong in Go, or deep TypeScript experience and proven ability to pick up Go fast"),
    _r("05", 3, "skill", "required", "Solid React and Next.js"),
    _r("05", 4, "skill", "nice_to_have", "React Native experience"),
    _r("05", 5, "skill", "required",
       "Comfortable with webhook-driven, telephony and event-based systems, debugging async flows across service boundaries"),
    _r("05", 6, "soft", "required", "Able to read and navigate a large, unfamiliar codebase independently"),
    _r("05", 7, "skill", "required", "Strong SQL and comfort operating PostgreSQL in production"),
    _r("05", 8, "language", "required", ENGLISH, language="english", cefr="C1"),
    _r("05", 9, "condition", "required", "Based in Latin America with at least 6 hours of overlap with US Pacific time"),
    _r("05", 10, "skill", "nice_to_have", "Telnyx or Twilio programmable voice and messaging experience"),
    _r("05", 11, "skill", "nice_to_have", "Experience building LLM-powered features"),
    # --- 12 Back-end Software Engineer (Python / Django) ---
    _r("12", 1, "experience", "required", "4+ years building backends with Python and Django", min_years=4),
    _r("12", 2, "skill", "required", "Solid experience with PostgreSQL in production, including schema changes on live systems"),
    _r("12", 3, "skill", "required", "Hands-on experience with background processing (Celery, RabbitMQ, Redis or similar)"),
    _r("12", 4, "skill", "required",
       "Built and maintained integrations with third-party APIs and knows what happens when they fail"),
    _r("12", 5, "skill", "required", "Cares about testing, code quality and constructive code reviews"),
    _r("12", 6, "skill", "required", "Has supported own work in production: monitoring, debugging and incidents"),
    _r("12", 7, "soft", "required", "Comfortable in a large codebase shared with many engineers"),
    _r("12", 8, "language", "required", ENGLISH, language="english", cefr="C1"),
    _r("12", 9, "skill", "nice_to_have", "Experience in the travel industry (hotels, airlines, cruises, booking systems)"),
    _r("12", 10, "skill", "nice_to_have", "Experience with payments or financial flows (Stripe, invoicing, payouts)"),
    _r("12", 11, "skill", "nice_to_have", "Has shipped AI-powered features to real users"),
    _r("12", 12, "skill", "nice_to_have", "Familiarity with Docker, Kubernetes or AWS"),
]
