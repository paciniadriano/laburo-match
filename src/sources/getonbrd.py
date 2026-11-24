"""Get on Board public API (free, no key).

Its terms (https://www.getonbrd.com/help/how-can-i-use-get-on-board-public-api-to-show-jobs-on-my-site):
credit "Get on Board" and link each job to its page, send applicants there, show job data as the
API returns it, and stay under the rate limit (20 requests per 5 seconds per IP at the time of
writing, not a contractual number). The host is fixed here: nothing a user or a posting says can
make the server call another address.
"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from src.core import clock
from src.sources.base import SourceJob, SourceQuery, SourceResult
from src.sources.html_text import html_to_text

BASE_URL = "https://www.getonbrd.com/api/v0"
PER_PAGE = 120  # the API silently caps larger values at 120
MAX_PAGES_PER_CATEGORY = 5  # ~288 jobs today in the largest category: 3 pages
MAX_RETRIES_ON_429 = 2
DEFAULT_BACKOFF_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 30.0
_CATEGORY = re.compile(r"^[a-z0-9-]{1,40}$")
# Same sections and order as the fixtures the eligibility labels were written on.
_SECTIONS = (
    "description_headline",
    "description",
    "projects",
    "functions",
    "desirable",
    "benefits",
)

Sleep = Callable[[float], Awaitable[None]]


def page_params(page: int, per_page: int = PER_PAGE) -> dict[str, str | int]:
    """Query string of one jobs page; `expand` adds the company (its name) to each job."""
    return {"per_page": per_page, "page": page, "expand": '["company"]'}


def _dig(obj: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def build_body(attributes: dict[str, Any]) -> str:
    blocks = []
    for section in _SECTIONS:
        text = html_to_text(str(attributes.get(section) or ""))
        if text:
            blocks.append(f"[{section}]\n{text}")
    return "\n\n".join(blocks)


def parse_job(item: Any) -> SourceJob | None:
    """Turn one API item into a `SourceJob`; None if it lacks what we cannot do without."""
    attributes = _dig(item, "attributes")
    external_id = _dig(item, "id")
    url = _dig(item, "links", "public_url")
    title = _dig(attributes, "title")
    if not (isinstance(external_id, str) and isinstance(url, str) and isinstance(title, str)):
        return None
    countries = attributes.get("countries")
    published = attributes.get("published_at")
    return SourceJob(
        source="getonbrd",
        external_id=external_id,
        title=title,
        company=str(_dig(attributes, "company", "data", "attributes", "name") or ""),
        url=url,
        apply_url=url,  # applicants apply on Get on Board's page: its terms say so
        location_text=", ".join(countries) if isinstance(countries, list) else "",
        body=build_body(attributes),
        language=str(attributes.get("lang") or ""),
        posted_at=datetime.fromtimestamp(published, UTC) if isinstance(published, int) else None,
    )


class GetOnBoardSource:
    name = "getonbrd"

    def __init__(self, client: httpx.AsyncClient, sleep: Sleep = asyncio.sleep) -> None:
        self._client = client
        self._sleep = sleep

    async def fetch(self, query: SourceQuery) -> SourceResult:
        jobs: dict[str, SourceJob] = {}
        warnings: list[str] = []
        for category in query.categories:
            if len(jobs) >= query.max_jobs:
                break
            if not _CATEGORY.match(category):
                warnings.append(f"Get on Board: invalid category {category!r}, skipped.")
                continue
            await self._fetch_category(category, query.max_jobs, jobs, warnings)
        return SourceResult(list(jobs.values())[: query.max_jobs], warnings)

    async def _fetch_category(
        self, category: str, max_jobs: int, jobs: dict[str, SourceJob], warnings: list[str]
    ) -> None:
        skipped = 0
        for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
            payload = await self._get_page(category, page, warnings)
            if payload is None:
                break
            items = payload.get("data")
            for item in items if isinstance(items, list) else []:
                job = parse_job(item)
                if job is None:
                    skipped += 1
                else:
                    jobs.setdefault(job.external_id, job)
            total_pages = _dig(payload, "meta", "total_pages")
            if not items or len(jobs) >= max_jobs or not isinstance(total_pages, int):
                break
            if page >= total_pages:
                break
        if skipped:
            warnings.append(f"Get on Board: {skipped} malformed job(s) skipped.")

    async def _get_page(
        self, category: str, page: int, warnings: list[str]
    ) -> dict[str, Any] | None:
        url = f"{BASE_URL}/categories/{category}/jobs"
        params = page_params(page)
        for attempt in range(MAX_RETRIES_ON_429 + 1):
            try:
                response = await self._client.get(url, params=params)
            except httpx.TimeoutException:
                warnings.append("Get on Board did not answer in time.")
                return None
            except httpx.HTTPError as error:
                warnings.append(f"Get on Board request failed ({type(error).__name__}).")
                return None
            if response.status_code == 429:
                if attempt < MAX_RETRIES_ON_429:
                    await self._sleep(_backoff_seconds(response))
                    continue
                warnings.append("Get on Board is limiting requests; try again in a few minutes.")
                return None
            if response.status_code != 200:
                warnings.append(f"Get on Board answered HTTP {response.status_code}.")
                return None
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if not isinstance(payload, dict):
                warnings.append("Get on Board returned an unreadable answer.")
                return None
            return payload
        return None  # unreachable: the loop always returns; keeps the type checker satisfied


def _backoff_seconds(response: httpx.Response) -> float:
    try:
        return min(float(response.headers["Retry-After"]), MAX_BACKOFF_SECONDS)
    except KeyError, ValueError:
        return DEFAULT_BACKOFF_SECONDS


class GetOnBoardReplay:
    """Demo mode: serves a recorded page instead of calling the API.

    Dates are moved forward so the newest recorded job reads as published now. Otherwise the
    freshness filter would, a month later, discard the whole demo. It ignores the query: the
    recording holds one category.
    """

    name = "getonbrd"

    def __init__(self, recorded_page: Path) -> None:
        self._payload: dict[str, Any] = json.loads(recorded_page.read_text(encoding="utf-8"))

    async def fetch(self, query: SourceQuery) -> SourceResult:
        parsed = [parse_job(item) for item in self._payload.get("data", [])]
        jobs = [job for job in parsed if job is not None]
        dated = [job.posted_at for job in jobs if job.posted_at is not None]
        if dated:
            shift = clock.now() - max(dated)
            jobs = [
                replace(job, posted_at=job.posted_at + shift) if job.posted_at else job
                for job in jobs
            ]
        return SourceResult(jobs[: query.max_jobs])
