"""Typed result of the `screen_batch` tool."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class JobCard(BaseModel):
    job_id: str  # the canonical id: what every other tool takes
    title: str
    company: str
    source: str  # shown to the user: Get on Board requires naming it
    eligibility: Literal["eligible", "doubtful"]
    reason: str
    quotes: list[str]  # verbatim from the posting
    recruiter_questions: list[str]  # what to ask the employer when the verdict is doubtful
    warnings: list[str]
    apply_url: str  # the best route: the page where the user applies
    posted_at: datetime | None


class ScreenBatchResult(BaseModel):
    """While `remaining > 0` only the counters are filled; the call that finishes adds the rest."""

    status: Literal["in_progress", "done"]
    processed: int  # jobs that got a verdict
    failed: int  # jobs that could not be processed after a retry
    remaining: int  # jobs still waiting or being processed
    next_step_hint: str
    shortlist: list[JobCard] = []
    eligible_total: int = 0
    doubtful_total: int = 0
    discarded: dict[str, int] = {}  # by reason, including "not_eligible"
    profile_questions: list[str] = []  # aggregated: asked once, not job by job
    disclaimer: str = ""
