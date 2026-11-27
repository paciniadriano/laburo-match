"""Run the eligibility eval: the same path as `screen_batch`, minus the database.

Posting text -> `job_extraction` (LLM) -> quote verification -> eligibility verdict (code).
The facts are cached in the LLM layer (see `llm/eval_cache.py`), not in Postgres.
"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evals.metrics.eligibility import Outcome
from src import llm
from src.app.eligibility.rules import evaluate_eligibility
from src.app.jobs.verify import verify_facts
from src.config.constants import JOB_TEXT_MAX_CHARS
from src.core.errors import BudgetExceededError, LLMOutputError
from src.llm.backend import Usage
from src.llm.tasks import JOB_EXTRACTION
from src.models.job_facts import JobFacts
from src.models.profile import Constraints

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
    usage: Usage = field(default_factory=Usage)


def load_dataset(dataset: str, split: str) -> dict[str, Any]:
    return json.loads((DATASETS / split / f"{dataset}.json").read_text())


def posting_text_as_served(fixture: str) -> str:
    """The text the server would show the model for this posting: `title`, newline, body.

    The fixtures keep the spike's header (job number, `title:` and a line of aggregator
    metadata such as `countries=['Chile']`). The live adapter never passes that metadata on, so
    leaving it in would hand the model facts the product does not have and flatter the eval.
    A file without that header is used as it is.
    """
    lines = fixture.splitlines()
    title, body_start = "", 0
    for index, line in enumerate(lines[:4]):
        if line.startswith("title: "):
            title = line.removeprefix("title: ")
        elif line.startswith("aggregator fields:"):
            body_start = index + 1
    if not title or not body_start:
        return fixture
    return f"{title}\n" + "\n".join(lines[body_start:]).strip()


async def classify(item: dict[str, Any], constraints: Constraints) -> tuple[Outcome, Usage]:
    text = posting_text_as_served((REPO_ROOT / item["fixture"]).read_text())[:JOB_TEXT_MAX_CHARS]
    result = await llm.run(JOB_EXTRACTION.name, text)
    assert isinstance(result.output, JobFacts)
    facts = verify_facts(result.output, text).facts  # quotes the model made up are dropped
    verdict = evaluate_eligibility(facts, constraints)
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

    await asyncio.gather(*(one(item) for item in items))
    report.outcomes.sort(key=lambda o: o.job)
    return report
