"""`make eval`: run an eval on a dataset split and print what it measured.

    python -m evals.run_eval --dataset eligibility --split dev [--budget 0.50] [--no-cache]

It costs real money (small: cents), so it is manual only. The default budget is a safety net:
the run stops calling the model when it is spent and says which items it did not judge.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from evals.eligibility_run import REPO_ROOT, RunReport, load_dataset, run_items
from evals.metrics.eligibility import CLASSES, Scores, score
from src import llm
from src.config.settings import get_settings
from src.core import clock
from src.core.usage import BudgetGuard
from src.llm.backend import LLMBackend
from src.llm.budget import BudgetedBackend
from src.llm.eval_cache import CachingBackend
from src.llm.runner import get_backend
from src.llm.tasks import JOB_EXTRACTION
from src.llm.versioning import resolve_model, version_hash

CACHE_DIR = REPO_ROOT / ".cache" / "evals" / "llm"
RESULTS_DIR = REPO_ROOT / "evals" / "results"


def build_backend(
    real: LLMBackend, guard: BudgetGuard, cache_dir: Path | None
) -> BudgetedBackend | CachingBackend:
    """Budget closest to the provider, cache outside it: a cache hit never reaches the guard."""
    budgeted = BudgetedBackend(real, guard)
    return CachingBackend(budgeted, cache_dir) if cache_dir else budgeted


def format_report(scores: Scores, run: RunReport, extra: dict[str, str]) -> str:
    lines = [f"{key}: {value}" for key, value in extra.items()]
    lines.append(f"items judged: {scores.total}  accuracy: {scores.accuracy:.0%}")
    if run.prefiltered:
        lines.append(f"discarded by the prefilter, no LLM call: {run.prefiltered}")
    lines.append("")
    lines.append(f"{'class':<14}{'precision':>10}{'recall':>9}{'support':>9}")
    for name in CLASSES:
        c = scores.per_class[name]
        precision = "n/a" if c.precision is None else f"{c.precision:.0%}"
        recall = "n/a" if c.recall is None else f"{c.recall:.0%}"
        lines.append(f"{name:<14}{precision:>10}{recall:>9}{c.support:>9}")
    lines.append("")
    lines.append("confusion (rows: expected, columns: predicted)")
    lines.append(f"{'':<14}" + "".join(f"{c:>14}" for c in CLASSES))
    for expected in CLASSES:
        row = "".join(f"{scores.confusion[expected][p]:>14}" for p in CLASSES)
        lines.append(f"{expected:<14}{row}")
    lines.append("")
    gate = "PASS" if not scores.wrongly_discarded else f"FAIL {scores.wrongly_discarded}"
    lines.append(f"valid jobs marked not_eligible (must be 0): {gate}")
    for outcome in run.outcomes:
        if outcome.expected != outcome.predicted:
            lines.append(
                f"  job {outcome.job}: expected {outcome.expected}, got {outcome.predicted}"
            )
            lines.append(f"    {outcome.reason}")
    if run.failed:
        lines.append(f"not judged (model error): {run.failed}")
    if run.skipped_for_budget:
        lines.append(f"not judged (budget spent): {run.skipped_for_budget}")
    return "\n".join(lines)


async def main(args: argparse.Namespace) -> int:
    settings = get_settings()
    guard = BudgetGuard(args.budget)
    cache_dir = None if args.no_cache else CACHE_DIR
    backend = build_backend(get_backend(), guard, cache_dir)

    dataset = load_dataset(args.dataset, args.split)
    with llm.use_backend(backend):
        run = await run_items(dataset["items"], concurrency=settings.llm_concurrency)
    scores = score(run.outcomes)

    cache_note = (
        "off"
        if isinstance(backend, BudgetedBackend)
        else (f"{backend.hits} hits, {backend.misses} misses")
    )
    extra = {
        "dataset": f"{args.dataset} / {args.split}",
        "model": resolve_model(JOB_EXTRACTION, settings),
        "version_hash": version_hash(JOB_EXTRACTION, settings)[:12],
        "cache": cache_note,
        "cost": f"${guard.spent_usd:.4f} of ${guard.limit_usd:.2f}",
    }
    print(format_report(scores, run, extra))

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = clock.now().strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"{args.dataset}-{args.split}-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                **extra,
                "accuracy": scores.accuracy,
                "confusion": scores.confusion,
                "wrongly_discarded": scores.wrongly_discarded,
                "outcomes": [vars(o) for o in run.outcomes],
            },
            indent=2,
        )
    )
    print(f"\nsaved: {path.relative_to(REPO_ROOT)}")
    return 1 if scores.wrongly_discarded or run.skipped_for_budget else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["eligibility"], required=True)
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--budget", type=float, default=0.50, help="USD; the run stops at it")
    parser.add_argument("--no-cache", action="store_true", help="ignore the eval cache")
    sys.exit(asyncio.run(main(parser.parse_args())))
