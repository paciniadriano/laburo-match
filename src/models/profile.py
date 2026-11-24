"""Typed shape of the profile's JSONB blocks (the subset phase 2 needs; phase 3 extends it).

`None` means "never asked", which is different from a confirmed empty value (`[]`). Unknown
values can only make a job `doubtful`; a confirmed empty value can make it `not_eligible`.
"""

from typing import Literal

from pydantic import BaseModel

Modality = Literal["remote", "hybrid", "onsite"]


class Constraints(BaseModel):
    country: str | None = None  # ISO 3166-1 alpha-2, e.g. "AR"
    citizenships: list[str] | None = None
    work_authorizations: list[str] | None = None  # countries or regions, e.g. "AR", "EU"
    accepted_modalities: list[Modality] | None = None


class Preferences(BaseModel):
    target_roles: list[str] | None = None


class Exclusions(BaseModel):
    max_job_age_days: int | None = None
