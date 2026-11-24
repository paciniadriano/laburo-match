"""`search_jobs`: fetch, store, filter and queue jobs for one user.

Read it as the steps of the tool; each one is a named function in `app/`. It does not commit:
the caller owns the transaction, so a search is saved whole or not at all.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.jobs.store import upsert_shared_jobs
from src.app.search.fetch import fetch_all
from src.app.search.plan import build_plan
from src.app.search.runs import create_run, job_ids_already_seen
from src.app.search.selection import select_for_screening
from src.config.constants import SEARCH_FETCH_LIMIT
from src.config.settings import Settings
from src.core import clock
from src.core.errors import ProfileRequiredError
from src.db.models import Profile
from src.models.profile import Exclusions, Preferences
from src.models.search import SearchSummary
from src.sources.base import JobSource, SourceQuery


async def search_jobs(
    session: AsyncSession,
    sources: list[JobSource],
    settings: Settings,
    user_id: UUID,
    max_new: int = 30,
) -> SearchSummary:
    # 1. Only a complete profile can search.
    profile = await session.get(Profile, user_id)
    if profile is None or not profile.is_complete:
        raise ProfileRequiredError()
    preferences = Preferences.model_validate(profile.preferences)
    exclusions = Exclusions.model_validate(profile.exclusions)
    now = clock.now()

    # 2. Plan, ask the sources, and store what they returned.
    plan = build_plan(preferences)
    fetched = await fetch_all(sources, SourceQuery(plan.categories, SEARCH_FETCH_LIMIT))
    stored = await upsert_shared_jobs(session, fetched.jobs, now)

    # 3. Keep what is new for this user, then filter, rank and cap it.
    seen = await job_ids_already_seen(session, user_id, [job.job_id for job in stored])
    fresh = [job for job in stored if job.job_id not in seen]
    selection = select_for_screening(
        fresh,
        plan.target_roles,
        now,
        max_age_days=exclusions.max_job_age_days or settings.job_max_age_days,
        limit=max(1, min(max_new, settings.max_new_jobs_per_search)),
    )

    # 4. Save the run and report.
    funnel = {
        "fetched": len(stored),
        "by_source": fetched.by_source,
        "already_seen": len(seen),
        "discarded": selection.discard_counts,
        "to_screen": len(selection.to_screen),
        "over_cap": len(selection.left_for_later),
    }
    run = await create_run(session, user_id, plan, selection, funnel, now)
    return SearchSummary(
        run_id=str(run.id),
        **funnel,
        plan_summary=plan.summary(),
        warnings=fetched.warnings,
        next_step_hint=(
            "Call screen_batch with this run_id until nothing remains."
            if selection.to_screen
            else "No new jobs since the last search."
        ),
    )
