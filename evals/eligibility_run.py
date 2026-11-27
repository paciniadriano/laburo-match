"""Run the eligibility eval: the same path as `search_jobs` + `screen_batch`, minus the database.

Source fields -> prefilter (code; a discard ends there, with no LLM call) -> posting text ->
`job_extraction` (LLM) -> quote verification -> eligibility verdict (code). The facts are
cached in the LLM layer (see `llm/eval_cache.py`), not in Postgres.
"""

import ast
import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from evals.metrics.eligibility import Outcome
from src import llm
from src.app.eligibility.declared import Declared
from src.app.eligibility.rules import evaluate_eligibility
from src.app.jobs.candidate import Candidate
from src.app.jobs.verify import verify_facts
from src.app.search.prefilter import prefilter_reason
from src.config.constants import JOB_TEXT_MAX_CHARS
from src.core import clock
from src.core.errors import BudgetExceededError, LLMOutputError
from src.llm.backend import Usage
from src.llm.tasks import JOB_EXTRACTION
from src.models.job_facts import JobFacts
from src.models.profile import Constraints
from src.sources.base import SourceModality
from src.sources.getonbrd import declared_residence, normalize_modality

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS = REPO_ROOT / "evals" / "datasets"

# The dataset's "reference_profile" is prose; this is the same person as data. Remote only,
# like the seeded sample profile.
REFERENCE_CONSTRAINTS = Constraints(
    country="AR",
    citizenships=["AR"],
    work_authorizations=["AR"],
    accepted_modalities=["remote"],
)


@dataclass
class RunReport:
    outcomes: list[Outcome] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # job -> why it could not be judged
    skipped_for_budget: list[str] = field(default_factory=list)
    prefiltered: list[str] = field(default_factory=list)  # discarded before any LLM call
    usage: Usage = field(default_factory=Usage)


def load_dataset(dataset: str, split: str) -> dict[str, Any]:
    return json.loads((DATASETS / split / f"{dataset}.json").read_text())


@dataclass(frozen=True)
class FixturePosting:
    title: str
    body: str
    modality: SourceModality  # what the source declared, as the adapter would store it
    location_text: str  # the source's countries, as the adapter would store them
    residence: str  # who may apply to a remote job, as the adapter would store it


def parse_fixture(fixture: str) -> FixturePosting | None:
    """Split a spike fixture into the posting text and the source's own fields.

    The header (job number, `title:`, a line of aggregator metadata) is not posting text: the
    server never shows it to the model. Its modality and countries are what the adapter stores
    as structured fields, and they reach the prefilter, as in production. None when the file
    has no such header.
    """
    lines = fixture.splitlines()
    title, meta, body_start = "", "", 0
    for index, line in enumerate(lines[:4]):
        if line.startswith("title: "):
            title = line.removeprefix("title: ")
        elif line.startswith("aggregator fields:"):
            meta, body_start = line, index + 1
    if not title or not body_start:
        return None
    modality = re.search(r"remote_modality=(\S+)", meta)
    countries = re.search(r"countries=(\[.*?\])", meta)
    names = ast.literal_eval(countries.group(1)) if countries else []
    declared_modality = modality.group(1) if modality else None
    return FixturePosting(
        title=title,
        body="\n".join(lines[body_start:]).strip(),
        modality=normalize_modality(declared_modality),
        location_text=", ".join(names),
        # The spike fixtures predate the expanded `location_tenants`, so a "locally remote" job
        # has no list here, as an old recording would have none.
        residence=declared_residence({"remote_modality": declared_modality}),
    )


def posting_text_as_served(fixture: str) -> str:
    """The text the server would show the model: `title`, newline, body. A file without the
    spike header is used as it is."""
    posting = parse_fixture(fixture)
    return f"{posting.title}\n{posting.body}" if posting else fixture


def prefiltered_reason(posting: FixturePosting | None, constraints: Constraints) -> str | None:
    """The search prefilter on the source's fields. The age checks do not apply: a fixture has
    no date, and a job without a date is always kept."""
    if posting is None:
        return None
    candidate = Candidate(
        uuid4(), posting.title, None, None, posting.modality, posting.location_text, posting.body,
        "", posting.residence,
    )  # fmt: skip
    return prefilter_reason(candidate, clock.now(), max_age_days=30, country=constraints.country)


def _declared(posting: FixturePosting | None) -> Declared | None:
    """The source fields as the screening step reads them from the `jobs` row."""
    if posting is None or posting.modality == "unknown":
        return None
    offices = posting.location_text if posting.modality in ("hybrid", "onsite") else ""
    return Declared("Get on Board", posting.modality, offices, posting.residence)


async def classify(item: dict[str, Any], constraints: Constraints) -> tuple[Outcome, Usage]:
    fixture = (REPO_ROOT / item["fixture"]).read_text()
    reason = prefiltered_reason(parse_fixture(fixture), constraints)
    if reason:
        message = f"Discarded by the search prefilter ({reason}), before any LLM call."
        return Outcome(item["job"], item["verdict"], "not_eligible", message), Usage()
    text = posting_text_as_served(fixture)[:JOB_TEXT_MAX_CHARS]
    posting = parse_fixture(fixture)
    result = await llm.run(JOB_EXTRACTION.name, text)
    assert isinstance(result.output, JobFacts)
    facts = verify_facts(result.output, text).facts  # quotes the model made up are dropped
    verdict = evaluate_eligibility(facts, constraints, _declared(posting))
    outcome = Outcome(item["job"], item["verdict"], verdict.verdict, verdict.reason)
    return outcome, result.usage


async def run_items(
    items: list[dict[str, Any]],
    constraints: Constraints = REFERENCE_CONSTRAINTS,
    concurrency: int = 4,
) -> RunReport:
    report = RunReport()
    gate = asyncio.Semaphore(concurrency)

    async def one(item: dict[str, Any]) -> None:
        async with gate:
            try:
                outcome, usage = await classify(item, constraints)
            except BudgetExceededError:
                report.skipped_for_budget.append(item["job"])
            except LLMOutputError as error:
                report.failed[item["job"]] = error.message
            else:
                report.outcomes.append(outcome)
                report.usage += usage
                if outcome.reason.startswith("Discarded by the search prefilter"):
                    report.prefiltered.append(outcome.job)

    await asyncio.gather(*(one(item) for item in items))
    report.outcomes.sort(key=lambda o: o.job)
    report.prefiltered.sort()
    return report
