"""Record one real Get on Board page as a demo/test fixture.

    uv run python -m scripts.record_fixtures

The raw answer is written outside the repo; only the scrubbed copy goes into `fixtures/`.
One request, no key. Manual only: fixtures are recorded on purpose, never by tests.
"""

import asyncio
import json
from pathlib import Path

from scripts.scrub_fixtures import find_contact_data, scrub_json_values
from src.core.http import make_http_client
from src.sources.getonbrd import BASE_URL, page_params
from src.sources.registry import GETONBRD_RECORDING

RAW_DIR = Path.home() / ".cache" / "laburo-match" / "raw"  # outside the repository
JOBS_PER_FIXTURE = 30  # enough for a demo, small enough to review and to keep the repo light


async def main() -> None:
    async with make_http_client() as client:
        response = await client.get(
            f"{BASE_URL}/categories/programming/jobs", params=page_params(1, JOBS_PER_FIXTURE)
        )
        response.raise_for_status()
        payload = response.json()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "getonbrd-page-1.json").write_text(json.dumps(payload), encoding="utf-8")

    scrubbed = scrub_json_values(payload)
    GETONBRD_RECORDING.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(scrubbed, ensure_ascii=False, indent=1) + "\n"
    GETONBRD_RECORDING.write_text(text, encoding="utf-8")
    print(
        f"Recorded {len(payload['data'])} jobs; contact items before scrubbing: "
        f"{len(find_contact_data(json.dumps(payload, ensure_ascii=False)))}, "
        f"after: {len(find_contact_data(text))}. Wrote {GETONBRD_RECORDING}"
    )


if __name__ == "__main__":
    asyncio.run(main())
