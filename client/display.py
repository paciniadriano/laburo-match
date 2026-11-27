"""What the terminal prints. The shortlist comes from the tool's structured result, never from
the model: links and quotes must reach the user exactly as the server verified them."""

from collections.abc import Callable
from typing import Any

from fastmcp.client.client import CallToolResult

from src.models.screening import JobCard, ScreenBatchResult

Printer = Callable[[str], None]

_BADGE = {"eligible": "ELIGIBLE", "doubtful": "DOUBTFUL"}


def format_card(position: int, card: JobCard) -> str:
    lines = [f"{position:>2}. [{_BADGE[card.eligibility]}] {card.title} - {card.company}"]
    lines.append(f"    {card.reason}")
    lines += [f'    "{quote}"' for quote in card.quotes]
    lines += [f"    Ask the recruiter: {question}" for question in card.recruiter_questions]
    lines += [f"    Warning: {warning}" for warning in card.warnings]
    lines.append(f"    Apply ({card.source}): {card.apply_url}")
    return "\n".join(lines)


def format_shortlist(result: ScreenBatchResult) -> str:
    header = f"Shortlist: {result.eligible_total} eligible, {result.doubtful_total} doubtful"
    cards = [format_card(n, card) for n, card in enumerate(result.shortlist, start=1)]
    footer = [result.disclaimer] if result.disclaimer else []
    return "\n\n".join([header, *cards, *footer])


def show_tool_result(name: str, result: CallToolResult, out: Printer = print) -> None:
    """Print progress for each tool call and the full shortlist when screening finishes."""
    data: Any = result.structured_content
    if result.is_error or data is None:
        return
    if name == "search_jobs":
        out(f"  [search] {data['to_screen']} jobs to screen")
    elif name == "screen_batch":
        screened = ScreenBatchResult.model_validate(data)
        if screened.status == "in_progress":
            out(f"  [screen] {screened.processed} done, {screened.remaining} remaining")
        else:
            out(format_shortlist(screened))
