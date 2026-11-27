"""Manual check of the real LLM path (costs a few cents): `uv run python -m scripts.llm_smoke 04`.

Runs `job_extraction` twice on one fixture posting so the second call shows prompt-cache hits.
Not part of `make test`: tests never call a real provider.
"""

import asyncio
import sys
from pathlib import Path

from src import llm
from src.app.jobs.verify import verify_facts
from src.models.job_facts import JobFacts

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "postings" / "getonbrd"


def load_posting(number: str) -> str:
    """Title line plus the body after the header block (the raw API fields are not the posting)."""
    lines = (FIXTURES / f"{number}.txt").read_text().split("\n")
    title = next(line for line in lines if line.startswith("title: "))
    return f"{title}\n\n" + "\n".join(lines[lines.index("") + 1 :])


async def main(number: str) -> None:
    text = load_posting(number)
    for call in (1, 2):
        result = await llm.run("job_extraction", text)
        usage = result.usage
        print(
            f"call {call}: model={result.model} attempts={result.attempts} "
            f"in={usage.input_tokens} (cached {usage.cached_tokens}) out={usage.output_tokens}"
        )
    assert isinstance(result.output, JobFacts)
    verified = verify_facts(result.output, text)
    print(
        f"verification: quotes dropped={verified.quotes_dropped}, "
        f"downgraded={verified.restrictions_downgraded}, email rejected={verified.email_rejected}"
    )
    print(verified.facts.model_dump_json(indent=1))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "04"))
