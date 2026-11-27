"""What the eligibility check returns."""

from dataclasses import dataclass, field
from typing import Literal

Verdict = Literal["eligible", "doubtful", "not_eligible"]

DISCLAIMER = (
    "Eligibility is an estimate based on the posting text, not legal advice; "
    "confirm with the employer."
)


@dataclass(frozen=True)
class EligibilityResult:
    verdict: Verdict
    reason: str
    quotes: list[str] = field(default_factory=list)  # verbatim, from the posting
    profile_questions: list[str] = field(default_factory=list)  # for the user
    recruiter_questions: list[str] = field(default_factory=list)  # for the employer
    warnings: list[str] = field(default_factory=list)  # shown on the card, no effect on the verdict
