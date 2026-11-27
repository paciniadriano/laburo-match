"""Typed result of the `list_jobs` tool."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ListStatus = Literal["all", "filtered"]


class ListedJob(BaseModel):
    job_id: str  # the canonical id: what every other tool takes
    title: str
    company: str
    source: str  # shown to the user: Get on Board requires naming it
    verdict: Literal["eligible", "doubtful", "not_eligible", "filtered"]
    reason: str  # why: the eligibility reason, or why the search left it out
    apply_url: str
    posted_at: datetime | None
    days_since_update: int  # days since it was judged
    closed: bool
    stale: bool  # judged with an older profile; it is re-checked before it is used again


class ListJobsResult(BaseModel):
    status: ListStatus
    items: list[ListedJob]
    total: int  # jobs in this status, across all pages
    offset: int
    has_more: bool
    next_step_hint: str
    disclaimer: str
