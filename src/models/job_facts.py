"""What the LLM extracts from one job posting (the output contract of `job_extraction`).

Everything here is a *proposal*: code verifies the quotes and the email against the posting
text before anything is used. Fields are never optional because strict structured output
requires every field; "nothing found" is an empty list or an empty string.
"""

from typing import Literal

from pydantic import BaseModel

RestrictionKind = Literal[
    "location",
    "citizenship",
    "work_authorization",
    "payroll",
    "timezone",
    "visa",
    "modality",
]
# explicit: stated directly. inferred: deduced from indirect signals.
# contradictory: the posting contradicts itself (both quotes are listed).
EvidenceKind = Literal["explicit", "inferred", "contradictory"]
PlaceScope = Literal["countries", "region", "worldwide", "not_applicable"]
WorkModality = Literal["remote", "hybrid", "onsite", "unknown"]


class Restriction(BaseModel):
    kind: RestrictionKind
    evidence_kind: EvidenceKind
    quotes: list[str]
    places: list[str]  # as written in the posting, e.g. ["Latin America"]
    place_scope: PlaceScope


class JobFacts(BaseModel):
    is_job_posting: bool
    language: str  # ISO 639-1 of the posting text, e.g. "es"
    work_modality: WorkModality
    restrictions: list[Restriction]
    office_locations: list[str]  # "City, Country" where the person must be present
    apply_email: str  # "" unless the posting states one
