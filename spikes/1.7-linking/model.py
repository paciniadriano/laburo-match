"""Data shapes for spike 1.7: what the profile knows (evidence) and what a posting asks (requirement)."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

# Fixed "today" so results are reproducible. In the server this comes from core.clock.now().
TODAY = date(2026, 11, 22)

# direct = the evidence IS that thing under any name (v1-v3 same + equivalent); related = similar but different,
# kept only as an argument for the user: it never changes the level.
Relation = Literal["direct", "same", "equivalent", "related"]
Level = Literal["met", "partial", "missing"]
Strength = Literal["detailed", "mention", "weak"]
ReqType = Literal["skill", "experience", "language", "education", "credential", "soft", "condition"]


@dataclass(frozen=True)
class Evidence:
    """One labelled fact from the CV (or the user). The LLM refers to it only by `id`."""

    id: str  # "E1", "E2", ...
    kind: Literal["experience", "skill", "project", "education", "certification", "language", "other"]
    name: str  # normalized name, e.g. "Node.js"
    # detailed = used in a job bullet; mention = only listed; weak = the CV itself qualifies it as weak
    # ("basic", "coursework", "familiar with", a vague summary claim): never enough for `met`
    strength: Strength
    # (start, end) pairs: start = first day of the first month, end = first day AFTER the last month
    # worked (exclusive), TODAY if ongoing. A skill used in two jobs has two periods; none = undated.
    periods: tuple[tuple[date, date], ...] = ()
    note: str = ""  # qualifier written in the CV: "basic", "coursework", ...
    cefr: str = ""  # language items only: A1..C2
    level_source: str = ""  # language items only: "certificate" | "self_assessed" | "native"


@dataclass(frozen=True)
class Requirement:
    """One requirement extracted from a posting (fixed input for this spike)."""

    key: str  # "p01-r03": posting + number, unique across the spike
    job: str
    type: ReqType
    required: Literal["required", "nice_to_have", "unspecified"]
    text: str  # normalized requirement, English
    min_years: float | None = None
    cefr: str = ""  # language requirements only
    language: str = ""  # language requirements only
    education_rank: str = ""  # education requirements only, see levels.EDUCATION_ORDER
    equivalent_experience_ok: bool = False  # "or equivalent experience"


@dataclass(frozen=True)
class Link:
    """What the LLM returns per requirement: one evidence ID and how it relates."""

    evidence_id: str
    relation: Relation


@dataclass(frozen=True)
class LevelResult:
    level: Level
    years: float | None = None  # union of the linked intervals, when it was computed
    gap_size: Literal["small", "large", ""] = ""  # only for partial caused by missing years / levels
    reason: str = ""  # short, machine-readable: why this level
