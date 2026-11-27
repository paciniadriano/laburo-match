"""What every job source has to provide, and the normalized job it returns."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

SourceModality = Literal["remote", "hybrid", "onsite", "unknown"]


@dataclass(frozen=True)
class SourceJob:
    """A posting in the shape of our `jobs` table, whichever source it came from."""

    source: str  # "getonbrd", "google_jobs"
    external_id: str  # the source's own id, unique per source
    title: str
    company: str
    url: str  # the posting's public page: also the attribution link the source's terms require
    apply_url: str
    location_text: str  # as the source states it: "Remote", "Chile"...
    body: str  # posting text as plain text, in sections
    language: str  # ISO 639-1
    posted_at: datetime | None
    # Where the work happens, as the source declares it (not read from the text). "unknown"
    # when the source does not say: never a reason to discard.
    modality: SourceModality = "unknown"
    # Who may apply to a remote job, as the source declares it: "anywhere", "Chile, Argentina",
    # or "" when it does not say.
    residence_text: str = ""


@dataclass(frozen=True)
class SourceQuery:
    categories: tuple[str, ...]
    max_jobs: int


@dataclass(frozen=True)
class SourceResult:
    jobs: list[SourceJob]
    # A failing source never fails the search: it explains itself here and returns what it got.
    warnings: list[str] = field(default_factory=list)


class JobSource(Protocol):
    name: str

    async def fetch(self, query: SourceQuery) -> SourceResult: ...
