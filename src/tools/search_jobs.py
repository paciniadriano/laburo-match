"""`search_jobs`: fetch, store, filter and queue jobs for one user.

It does not commit: the caller owns the transaction, so a search is saved whole or not at all.
"""

import asyncio
import logging
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.jobs.store import upsert_shared_jobs
from src.app.search.plan import build_plan
from src.app.search.prefilter import prefilter_reason
from src.app.search.relevance import rank
from src.config.constants import RUN_TTL_HOURS, SEARCH_FETCH_LIMIT
from src.config.settings import Settings
from src.core import clock
from src.core.errors import ProfileRequiredError
from src.db.models import Profile, RunJob, SearchRun
from src.models.profile import Exclusions, Preferences
from src.models.search import SearchSummary
from src.sources.base import JobSource, SourceJob, SourceQuery, SourceResult

logger = logging.getLogger(__name__)


async def _fetch(source: JobSource, query: SourceQuery) -> SourceResult:
    """A source is supposed to report problems as warnings; this catches the ones it did not."""
    try:
        return await source.fetch(query)
    except Exception:
        logger.exception("source failed unexpectedly", extra={"source": source.name})
        return SourceResult([], [f"{source.name}: unexpected error, skipped."])


async def search_jobs(
    session: AsyncSession,
    sources: list[JobSource],
    settings: Settings,
    user_id: UUID,
    max_new: int = 30,
) -> SearchSummary:
    profile = await session.get(Profile, user_id)
    if profile is None or not profile.is_complete:
        raise ProfileRequiredError()
    preferences = Preferences.model_validate(profile.preferences)
    exclusions = Exclusions.model_validate(profile.exclusions)
    max_age_days = exclusions.max_job_age_days or settings.job_max_age_days
    limit = max(1, min(max_new, settings.max_new_jobs_per_search))
    now = clock.now()

    plan = build_plan(preferences)
    query = SourceQuery(categories=plan.categories, max_jobs=SEARCH_FETCH_LIMIT)
    results = await asyncio.gather(*(_fetch(source, query) for source in sources))
    fetched: list[SourceJob] = [job for result in results for job in result.jobs]
    warnings = [warning for result in results for warning in result.warnings]
    by_source = {
        source.name: len(result.jobs) for source, result in zip(sources, results, strict=True)
    }

    stored = await upsert_shared_jobs(session, fetched, now)

    # New for this user = no row of theirs yet. Jobs left over a previous cap have none.
    known = set(
        await session.scalars(
            select(RunJob.job_id).where(
                RunJob.user_id == user_id, RunJob.job_id.in_([c.job_id for c in stored])
            )
        )
    )
    fresh = [c for c in stored if c.job_id not in known]

    discarded: list[tuple[UUID, str]] = []
    kept = []
    for candidate in fresh:
        reason = prefilter_reason(candidate, now, max_age_days)
        if reason:
            discarded.append((candidate.job_id, reason))
        else:
            kept.append(candidate)

    ranked = rank(kept, plan.target_roles)
    to_screen, left_for_later = ranked[:limit], ranked[limit:]
    discard_counts: dict[str, int] = {}
    for _, reason in discarded:
        discard_counts[reason] = discard_counts.get(reason, 0) + 1

    run = SearchRun(
        id=uuid4(),
        user_id=user_id,
        kind="search",
        plan=plan.to_json(),
        expires_at=now + timedelta(hours=RUN_TTL_HOURS),
        funnel={
            "fetched": len(stored),
            "by_source": by_source,
            "already_seen": len(stored) - len(fresh),
            "discarded": discard_counts,
            "to_screen": len(to_screen),
            "over_cap": len(left_for_later),
        },
    )
    session.add(run)
    await session.flush()  # the run must exist before the rows that point to it

    position = 0
    for candidate in to_screen:
        position += 1
        session.add(
            RunJob(run_id=run.id, job_id=candidate.job_id, user_id=user_id, position=position)
        )
    for job_id, reason in discarded:  # kept as `done` rows so every discard can be audited
        position += 1
        session.add(
            RunJob(
                run_id=run.id,
                job_id=job_id,
                user_id=user_id,
                position=position,
                status="done",
                prefilter_reason=reason,
                screened_at=now,
            )
        )
    await session.flush()

    return SearchSummary(
        run_id=str(run.id),
        fetched=len(stored),
        by_source=by_source,
        already_seen=len(stored) - len(fresh),
        discarded=discard_counts,
        to_screen=len(to_screen),
        over_cap=len(left_for_later),
        plan_summary=plan.summary(),
        warnings=warnings,
        next_step_hint=(
            "Call screen_batch with this run_id until nothing remains."
            if to_screen
            else "No new jobs since the last search."
        ),
    )
