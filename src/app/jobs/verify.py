"""Check the LLM's output against the posting text. Code, not the model, decides what is real.

Quotes must appear verbatim in the posting (whitespace aside) and `apply_email` must be a valid
address that appears in it. A restriction that loses its quotes can no longer justify a hard
verdict, so it is downgraded to `inferred`, which can only make a job `doubtful`.
"""

import re
from dataclasses import dataclass

from src.models.job_facts import JobFacts, Restriction

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# A contradiction needs two statements; any other kind needs at least one.
_MIN_QUOTES = {"explicit": 1, "contradictory": 2}


@dataclass(frozen=True)
class Verified:
    facts: JobFacts
    quotes_dropped: int  # quotes not found in the text (the model made them up or altered them)
    restrictions_downgraded: int
    email_rejected: bool


def _squash(text: str) -> str:
    """Collapse whitespace so a quote that spans a line break still matches."""
    return " ".join(text.split())


def verify_facts(facts: JobFacts, posting_text: str) -> Verified:
    haystack = _squash(posting_text)
    quotes_dropped = 0
    downgraded = 0
    restrictions: list[Restriction] = []

    for restriction in facts.restrictions:
        kept = [q for q in restriction.quotes if _squash(q) and _squash(q) in haystack]
        quotes_dropped += len(restriction.quotes) - len(kept)
        evidence_kind = restriction.evidence_kind
        if len(kept) < _MIN_QUOTES.get(evidence_kind, 0):
            evidence_kind = "inferred"
            downgraded += 1
        restrictions.append(
            restriction.model_copy(update={"quotes": kept, "evidence_kind": evidence_kind})
        )

    email = facts.apply_email
    email_rejected = bool(email) and not (_EMAIL.match(email) and email in posting_text)
    if email_rejected:
        email = ""

    verified = facts.model_copy(update={"restrictions": restrictions, "apply_email": email})
    return Verified(verified, quotes_dropped, downgraded, email_rejected)
