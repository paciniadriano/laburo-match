"""A stored job as seen by the search steps that filter and rank it."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Candidate:
    job_id: UUID
    title: str
    posted_at: datetime | None
    closed_at: datetime | None
    modality: str = "unknown"  # as the source declares it
    location_text: str = ""  # as the source declares it: "Chile", "Remote"...
    raw_text: str = ""  # the posting body, for the prefilter's look at the prose
    company: str = ""  # normalized ("acme inc"), "" when the source does not name it
