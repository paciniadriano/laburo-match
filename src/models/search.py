"""Typed result of the `search_jobs` tool."""

from pydantic import BaseModel


class SearchSummary(BaseModel):
    run_id: str
    fetched: int  # distinct jobs the sources returned
    by_source: dict[str, int]
    already_seen: int  # skipped: this user already judged them in an earlier search
    carried_over: int  # in to_screen: an earlier search left them unscreened
    discarded: dict[str, int]  # by reason, e.g. {"too_old": 4}
    to_screen: int  # jobs waiting for `screen_batch`
    over_cap: int  # new jobs left for a later search
    plan_summary: str
    warnings: list[str]
    next_step_hint: str
