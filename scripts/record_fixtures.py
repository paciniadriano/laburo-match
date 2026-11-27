"""Record every page of Get on Board's programming category as demo/test fixtures.

    uv run python -m scripts.record_fixtures     (or: make record-fixtures)

The raw answers are written outside the repo; only scrubbed copies go into `fixtures/`. No key
and no cost: Get on Board's API is free (SerpApi is not recorded here). Manual only: fixtures
are recorded on purpose, never by tests.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from scripts.scrub_fixtures import find_contact_data, scrub_json_values
from src.core.http import make_http_client
from src.sources.getonbrd import BASE_URL, page_params
from src.sources.registry import GETONBRD_RECORDINGS, recorded_pages

RAW_DIR = Path.home() / ".cache" / "laburo-match" / "raw"  # outside the repository
# 50 jobs per file keeps each one near 400 KB, under the 1 MB limit of the large-file hook.
JOBS_PER_PAGE = 50
MAX_PAGES = 20  # a safety stop: 1,000 jobs is far more than the category holds
SECONDS_BETWEEN_PAGES = 0.5  # the terms allow 20 requests per 5 s; this stays far below


async def fetch_all_pages() -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    async with make_http_client() as client:
        for number in range(1, MAX_PAGES + 1):
            response = await client.get(
                f"{BASE_URL}/categories/programming/jobs", params=page_params(number, JOBS_PER_PAGE)
            )
            response.raise_for_status()
            payload = response.json()
            pages.append(payload)
            total = (payload.get("meta") or {}).get("total_pages")
            if not payload.get("data") or not isinstance(total, int) or number >= total:
                break
            await asyncio.sleep(SECONDS_BETWEEN_PAGES)
    return pages


def write_pages(pages: list[dict[str, Any]]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    GETONBRD_RECORDINGS.mkdir(parents=True, exist_ok=True)
    for old in recorded_pages():  # a shorter recording must not leave stale pages behind
        old.unlink()
    before = after = jobs = 0
    for number, payload in enumerate(pages, start=1):
        raw = json.dumps(payload, ensure_ascii=False)
        (RAW_DIR / f"getonbrd-page-{number}.json").write_text(raw, encoding="utf-8")
        text = json.dumps(scrub_json_values(payload), ensure_ascii=False, indent=1) + "\n"
        (GETONBRD_RECORDINGS / f"page-{number}.json").write_text(text, encoding="utf-8")
        before += len(find_contact_data(raw))
        after += len(find_contact_data(text))
        jobs += len(payload.get("data", []))
    print(
        f"Recorded {jobs} jobs in {len(pages)} pages; contact items before scrubbing: {before}, "
        f"after: {after}. Wrote {GETONBRD_RECORDINGS}"
    )


async def main() -> None:
    write_pages(await fetch_all_pages())


if __name__ == "__main__":
    asyncio.run(main())
