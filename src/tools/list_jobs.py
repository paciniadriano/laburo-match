"""`list_jobs`: one page of the jobs the user already has a verdict for.

Read it as the steps of the tool. Read-only: it never re-screens. A verdict computed with an
older profile is only marked `stale`; the tools that use a job re-check it first.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.eligibility.result import DISCLAIMER
from src.app.jobs.listing import list_judged_jobs
from src.app.profile.store import load_constraints
from src.app.screening.screening_hash import screening_hash
from src.config.constants import LIST_JOBS_MAX_LIMIT
from src.core import clock
from src.models.listing import ListJobsResult, ListStatus


async def list_jobs_tool(
    session: AsyncSession,
    user_id: UUID,
    status: ListStatus = "all",
    limit: int = 20,
    offset: int = 0,
) -> ListJobsResult:
    # 1. The current profile tells which verdicts are stale.
    current_hash = screening_hash(await load_constraints(session, user_id))

    # 2. Read one page, within the size the host's context can take.
    limit = max(1, min(limit, LIST_JOBS_MAX_LIMIT))
    offset = max(0, offset)
    items, total = await list_judged_jobs(
        session, user_id, status, limit, offset, current_hash, clock.now()
    )

    # 3. Say whether there is more, and what the host should do with it.
    has_more = offset + len(items) < total
    return ListJobsResult(
        status=status,
        items=items,
        total=total,
        offset=offset,
        has_more=has_more,
        next_step_hint=_hint(status, has_more, offset + len(items)),
        disclaimer=DISCLAIMER,
    )


def _hint(status: ListStatus, has_more: bool, next_offset: int) -> str:
    what = (
        "These jobs were left out automatically; each reason says why."
        if status == "filtered"
        else "Show these jobs with their reason and apply link. Use the job_id of each one."
    )
    more = f" Call list_jobs with offset={next_offset} for the next page." if has_more else ""
    return what + more
