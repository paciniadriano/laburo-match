"""What the terminal prints for a shortlist."""

from client.display import format_shortlist
from src.models.screening import JobCard, ScreenBatchResult


def _card(n: int) -> JobCard:
    return JobCard(
        job_id=str(n),
        title=f"Role {n}",
        company="Acme",
        source="Get on Board",
        eligibility="doubtful",
        reason="The posting says nothing about where you can work from.",
        quotes=[],
        recruiter_questions=[],
        warnings=[],
        apply_url=f"https://example.com/{n}",
        posted_at=None,
    )


def _result(shown: int, eligible: int, doubtful: int) -> ScreenBatchResult:
    return ScreenBatchResult(
        status="done",
        processed=eligible + doubtful,
        failed=0,
        remaining=0,
        next_step_hint="",
        shortlist=[_card(n) for n in range(shown)],
        eligible_total=eligible,
        doubtful_total=doubtful,
    )


def test_the_header_says_when_cards_are_left_out():
    text = format_shortlist(_result(shown=10, eligible=1, doubtful=29))
    assert text.startswith("Shortlist: showing 10 of 30 (1 eligible, 29 doubtful)")


def test_the_header_is_plain_when_every_card_is_shown():
    text = format_shortlist(_result(shown=3, eligible=0, doubtful=3))
    assert text.startswith("Shortlist: 0 eligible, 3 doubtful")


def test_the_reasons_jobs_were_left_out_are_shown_in_words():
    result = _result(shown=1, eligible=1, doubtful=0).model_copy(
        update={"discarded": {"office_abroad": 20, "too_old": 0, "not_eligible": 2}}
    )

    text = format_shortlist(result)

    assert "Left out: 20 hybrid or on-site in another country, 2 not open to your country" in text


def test_a_listing_prints_one_line_per_job_with_its_link_and_says_when_more_exist():
    from client.display import format_listing
    from src.models.listing import ListedJob, ListJobsResult

    item = ListedJob(
        job_id="1", title="Frontend Engineer", company="Acme", source="Get on Board",
        verdict="doubtful", reason="The posting says nothing about where you can work from.",
        apply_url="https://example.com/1", posted_at=None, days_since_update=0, closed=False,
        stale=False,
    )  # fmt: skip
    result = ListJobsResult(
        status="all", items=[item], total=12, offset=10, has_more=True, next_step_hint="",
        disclaimer="",
    )  # fmt: skip

    text = format_listing(result)

    assert text.startswith("Jobs (all): 11-11 of 12")
    assert "11. [DOUBTFUL] Frontend Engineer - Acme" in text
    assert "Apply (Get on Board): https://example.com/1" in text
    assert text.endswith("Ask for more to see the next page.")
