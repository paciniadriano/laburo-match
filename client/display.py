"""What the terminal prints. The shortlist comes from the tool's structured result, never from
the model: links and quotes must reach the user exactly as the server verified them."""

from collections.abc import Callable
from typing import Any

from fastmcp.client.client import CallToolResult

from src.models.listing import ListJobsResult
from src.models.screening import JobCard, ScreenBatchResult

Printer = Callable[[str], None]

_BADGE = {"eligible": "ELIGIBLE", "doubtful": "DOUBTFUL"}

# Why jobs never reached the list, in words a person reads at a glance.
_DISCARD_LABELS = {
    "office_abroad": "hybrid or on-site in another country",
    "not_eligible": "not open to your country",
    "duplicate": "duplicate postings",
    "too_old": "too old",
    "closed": "closed",
}


def format_discards(discarded: dict[str, int]) -> str:
    parts = [f"{n} {_DISCARD_LABELS.get(reason, reason)}" for reason, n in discarded.items() if n]
    return f"Left out: {', '.join(parts)}" if parts else ""


def format_card(position: int, card: JobCard) -> str:
    lines = [f"{position:>2}. [{_BADGE[card.eligibility]}] {card.title} - {card.company}"]
    lines.append(f"    {card.reason}")
    lines += [f'    "{quote}"' for quote in card.quotes]
    lines += [f"    Ask the recruiter: {question}" for question in card.recruiter_questions]
    lines += [f"    Warning: {warning}" for warning in card.warnings]
    lines.append(f"    Apply ({card.source}): {card.apply_url}")
    return "\n".join(lines)


def format_shortlist(result: ScreenBatchResult) -> str:
    total = result.eligible_total + result.doubtful_total
    counts = f"{result.eligible_total} eligible, {result.doubtful_total} doubtful"
    # Say it when cards are left out: the totals would read as "these are all of them".
    if len(result.shortlist) < total:
        header = f"Shortlist: showing {len(result.shortlist)} of {total} ({counts})"
    else:
        header = f"Shortlist: {counts}"
    cards = [format_card(n, card) for n, card in enumerate(result.shortlist, start=1)]
    discards = format_discards(result.discarded)
    if result.remaining:
        more = [f"{result.remaining} more jobs not checked yet: ask for more."]
    else:
        more = ["Every job from this search is checked."]
    footer = [result.disclaimer] if result.disclaimer else []
    return "\n\n".join([header, *([discards] if discards else []), *cards, *more, *footer])


def format_listing(result: ListJobsResult) -> str:
    """One line per job, enough to choose; the cards with quotes are the shortlist's job."""
    first, last = result.offset + 1, result.offset + len(result.items)
    header = f"Jobs ({result.status}): {first}-{last} of {result.total}"
    lines = [
        f"{n:>3}. [{item.verdict.upper()}] {item.title} - {item.company}\n"
        f"     {item.reason}\n     Apply ({item.source}): {item.apply_url}"
        for n, item in enumerate(result.items, start=result.offset + 1)
    ]
    more = ["Ask for more to see the next page."] if result.has_more else []
    return "\n".join([header, *lines, *more]) if result.items else f"No jobs ({result.status})."


def show_tool_result(name: str, result: CallToolResult, out: Printer = print) -> None:
    """Print a line for each search and the shortlist after every screening round."""
    data: Any = result.structured_content
    if result.is_error or data is None:
        return
    if name == "search_jobs":
        out(f"  [search] {data['to_screen']} jobs to screen")
    elif name == "screen_batch":
        out(format_shortlist(ScreenBatchResult.model_validate(data)))
    elif name == "list_jobs":
        out(format_listing(ListJobsResult.model_validate(data)))
