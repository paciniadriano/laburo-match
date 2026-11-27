"""Extract the facts of one job, reusing the cached result whenever it is still valid.

The facts describe the posting, not the user, so one stored result serves every user. It is
valid while the posting text (`content_hash`), the LLM setup (`version_hash`) and the part of
the text the model reads (`chars_read`) are the same as when it was computed.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src import llm
from src.app.jobs.verify import verify_facts
from src.config.constants import JOB_TEXT_MAX_CHARS
from src.config.settings import get_settings
from src.db.models import Job, JobExtraction
from src.llm.backend import Usage
from src.llm.tasks import JOB_EXTRACTION
from src.llm.versioning import version_hash
from src.models.job_facts import JobFacts


@dataclass(frozen=True)
class Extracted:
    facts: JobFacts  # already verified against the posting text
    from_cache: bool
    usage: Usage  # zero when it came from the cache


def posting_text(job: Job) -> str:
    """The text the model reads (and the quotes are checked against), capped in size.

    The cap bounds cost and the room an attacker has to hide instructions in a long posting.
    """
    return f"{job.title}\n{job.raw_text}"[:JOB_TEXT_MAX_CHARS]


async def extract_job_facts(session: AsyncSession, job: Job) -> Extracted:
    """Cached facts if the text and the LLM setup are unchanged; otherwise one LLM call."""
    current_version = version_hash(JOB_EXTRACTION, get_settings())
    text = posting_text(job)
    # `chars_read` is what makes a changed size cap re-extract only the postings it cut: the
    # text is fixed by `content_hash`, so the same length means the same text was read.
    cached = await session.scalar(
        select(JobExtraction.facts).where(
            JobExtraction.job_id == job.id,
            JobExtraction.version_hash == current_version,
            JobExtraction.content_hash == job.content_hash,
            JobExtraction.chars_read == len(text),
            JobExtraction.status == "ok",
        )
    )
    if cached is not None:
        return Extracted(JobFacts.model_validate(cached), from_cache=True, usage=Usage())

    result = await llm.run(JOB_EXTRACTION.name, text)
    assert isinstance(result.output, JobFacts)
    facts = verify_facts(result.output, text).facts  # quotes the model made up are dropped here

    # Two calls may extract the same job at once; the first stored result wins.
    await session.execute(
        insert(JobExtraction)
        .values(
            job_id=job.id,
            version_hash=result.version_hash,
            content_hash=job.content_hash,
            status="ok",
            chars_read=len(text),
            facts=facts.model_dump(mode="json"),
        )
        .on_conflict_do_nothing()
    )
    return Extracted(facts, from_cache=False, usage=result.usage)
