"""Ask every source for jobs and gather the answers."""

import asyncio
import logging
from dataclasses import dataclass

from src.sources.base import JobSource, SourceJob, SourceQuery, SourceResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Fetched:
    jobs: list[SourceJob]
    warnings: list[str]
    by_source: dict[str, int]


async def _fetch(source: JobSource, query: SourceQuery) -> SourceResult:
    """A source is supposed to report problems as warnings; this catches the ones it did not."""
    try:
        return await source.fetch(query)
    except Exception:
        logger.exception("source failed unexpectedly", extra={"source": source.name})
        return SourceResult([], [f"{source.name}: unexpected error, skipped."])


async def fetch_all(sources: list[JobSource], query: SourceQuery) -> Fetched:
    results = await asyncio.gather(*(_fetch(source, query) for source in sources))
    return Fetched(
        jobs=[job for result in results for job in result.jobs],
        warnings=[warning for result in results for warning in result.warnings],
        by_source={
            source.name: len(result.jobs) for source, result in zip(sources, results, strict=True)
        },
    )
