"""The eligibility eval: scores, and the runner on small postings with a scripted model."""

from pathlib import Path

import pytest

from evals.eligibility_run import RunReport, posting_text_as_served, run_items
from evals.metrics.eligibility import Outcome, score
from evals.run_eval import format_report
from src import llm
from src.core.usage import BudgetGuard
from src.llm.backend import Usage
from src.llm.budget import BudgetedBackend
from src.llm.messages import Message
from src.llm.tasks import JOB_EXTRACTION
from tests.factories import make_facts, make_restriction
from tests.fakes.fake_llm import FakeLLM, InvalidOutput

LATAM_TEXT = "Remote within Latin America"
US_TEXT = "You must live in any US state"


def _facts_for(messages: list[Message]):
    """The model 'reads' the posting: a US-only text gets a US restriction, else LATAM."""
    posting = messages[-1][1]
    if US_TEXT in posting:
        return make_facts(
            restrictions=[
                make_restriction(quotes=[US_TEXT], places=["any US state"], place_scope="countries")
            ]
        )
    return make_facts(restrictions=[make_restriction(quotes=[LATAM_TEXT])])


def _item(directory: Path, job: str, text: str, expected: str) -> dict[str, str]:
    path = directory / f"{job}.txt"
    path.write_text(text)
    return {"job": job, "fixture": str(path), "verdict": expected}  # absolute: used as is


# --- scores ---------------------------------------------------------------------------------
def test_a_perfect_run_scores_one_everywhere_and_discards_nothing_valid():
    outcomes = [
        Outcome("1", "eligible", "eligible"),
        Outcome("2", "doubtful", "doubtful"),
        Outcome("3", "not_eligible", "not_eligible"),
    ]

    scores = score(outcomes)

    assert scores.accuracy == 1.0
    assert all(c.precision == 1.0 and c.recall == 1.0 for c in scores.per_class.values())
    assert scores.wrongly_discarded == []


def test_a_valid_job_called_not_eligible_is_listed_whether_it_was_eligible_or_doubtful():
    outcomes = [
        Outcome("1", "eligible", "not_eligible"),
        Outcome("2", "doubtful", "not_eligible"),
        Outcome("3", "not_eligible", "not_eligible"),  # a right discard is not a mistake
        Outcome("4", "not_eligible", "doubtful"),  # too cautious, but nothing valid was lost
    ]

    scores = score(outcomes)

    assert scores.wrongly_discarded == ["1", "2"]
    assert scores.per_class["not_eligible"].precision == pytest.approx(1 / 3)
    assert scores.per_class["not_eligible"].recall == pytest.approx(1 / 2)


def test_a_class_nobody_predicted_has_no_precision_instead_of_a_fake_zero():
    scores = score([Outcome("1", "eligible", "doubtful")])

    assert scores.per_class["eligible"].precision is None
    assert scores.per_class["eligible"].recall == 0.0
    assert scores.per_class["not_eligible"].recall is None  # no such items in the dataset


# --- runner ---------------------------------------------------------------------------------
async def test_the_runner_reads_each_posting_and_gets_the_verdict_from_code(
    tmp_path: Path, fake_llm: FakeLLM
):
    fake_llm.script(JOB_EXTRACTION.name, _facts_for, _facts_for, _facts_for)
    items = [
        _item(tmp_path, "a", LATAM_TEXT, "eligible"),
        _item(tmp_path, "b", US_TEXT, "not_eligible"),
        _item(tmp_path, "c", US_TEXT, "eligible"),  # a wrong label: the system will disagree
    ]

    report = await run_items(items, concurrency=2)

    assert [(o.job, o.predicted) for o in report.outcomes] == [
        ("a", "eligible"),
        ("b", "not_eligible"),
        ("c", "not_eligible"),
    ]
    assert score(report.outcomes).wrongly_discarded == ["c"]
    assert report.usage == Usage(input_tokens=300, output_tokens=60)  # the fake's default x3


async def test_an_item_the_model_cannot_answer_is_reported_not_hidden(
    tmp_path: Path, fake_llm: FakeLLM
):
    fake_llm.script(JOB_EXTRACTION.name, InvalidOutput(), InvalidOutput())  # first try + retry

    report = await run_items([_item(tmp_path, "a", LATAM_TEXT, "eligible")], concurrency=1)

    assert report.outcomes == []
    assert list(report.failed) == ["a"]


async def test_when_the_budget_is_spent_the_rest_is_skipped_and_listed(tmp_path: Path):
    expensive = FakeLLM(usage=Usage(input_tokens=1_000_000))  # $0.10 per call
    expensive.script(JOB_EXTRACTION.name, _facts_for, _facts_for)
    guard = BudgetGuard(limit_usd=0.05)
    items = [_item(tmp_path, n, LATAM_TEXT, "eligible") for n in ("a", "b", "c")]

    with llm.use_backend(BudgetedBackend(expensive, guard)):
        report = await run_items(items, concurrency=1)

    assert [o.job for o in report.outcomes] == ["a"]
    assert report.skipped_for_budget == ["b", "c"]
    assert len(expensive.calls) == 1


def test_the_report_states_the_gate_and_lists_each_disagreement():
    outcomes = [Outcome("7", "eligible", "not_eligible", "The posting restricts to Chile.")]

    text = format_report(score(outcomes), RunReport(outcomes=outcomes), {"cost": "$0.0010"})

    assert "valid jobs marked not_eligible (must be 0): FAIL ['7']" in text
    assert "job 7: expected eligible, got not_eligible" in text


# --- the text the model sees ------------------------------------------------------------------
SPIKE_FIXTURE = (
    "JOB 14 | raw_index=2\n"
    "title: Technical Lead (Python)\n"
    "aggregator fields: remote_modality=hybrid countries=['Chile'] lang=es\n"
    "\n"
    "[description_headline]\n"
    "Trabajamos en un entorno h\u00edbrido.\n"
)


def test_the_model_sees_the_title_and_body_but_not_the_aggregator_metadata():
    text = posting_text_as_served(SPIKE_FIXTURE)

    assert (
        text
        == "Technical Lead (Python)\n[description_headline]\nTrabajamos en un entorno h\u00edbrido."
    )
    assert "Chile" not in text and "aggregator" not in text and "JOB 14" not in text


def test_a_posting_without_the_spike_header_is_used_as_it_is():
    assert posting_text_as_served("Remote within Latin America") == "Remote within Latin America"
