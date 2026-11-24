from datetime import UTC, datetime

import httpx
import pytest
import respx

from src.sources.base import SourceQuery
from src.sources.getonbrd import BASE_URL, GetOnBoardSource
from tests.factories import gob_item, gob_page

JOBS_URL = f"{BASE_URL}/categories/programming/jobs"
QUERY = SourceQuery(categories=("programming",), max_jobs=500)


class Sleeps:
    """Records waits instead of sleeping, so retry tests run instantly."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield http


async def test_a_job_is_normalized_with_attribution_and_the_fixture_text_layout(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    respx_mock.get(JOBS_URL).respond(json=gob_page([gob_item("tech-lead-ff58")]))

    result = await GetOnBoardSource(client).fetch(QUERY)

    (job,) = result.jobs
    assert result.warnings == []
    assert (job.source, job.external_id, job.title) == (
        "getonbrd",
        "tech-lead-ff58",
        "Frontend Engineer",
    )
    assert job.company == "Acme"
    assert job.url == "https://www.getonbrd.com/jobs/tech-lead-ff58"  # the attribution link
    assert job.apply_url == job.url  # applicants are sent to Get on Board
    assert job.location_text == "Chile"
    assert job.language == "es"
    assert job.posted_at == datetime.fromtimestamp(1795535105, UTC)
    assert job.body == (
        "[description_headline]\nRequirements\n\n"
        "[description]\nReact experience\n- TypeScript\n\n"
        "[projects]\nWe build payments.\n\n"
        "[functions]\n- Build UIs\n\n"
        "[desirable]\nGraphQL\n\n"
        "[benefits]\n- Remote work"
    )


async def test_sections_without_text_are_left_out(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    respx_mock.get(JOBS_URL).respond(json=gob_page([gob_item(desirable="", benefits=None)]))

    (job,) = (await GetOnBoardSource(client).fetch(QUERY)).jobs

    assert "[desirable]" not in job.body
    assert "[benefits]" not in job.body


async def test_pages_are_requested_one_at_a_time_until_the_last(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    route = respx_mock.get(JOBS_URL).mock(
        side_effect=[
            httpx.Response(200, json=gob_page([gob_item("a")], page=1, total_pages=2)),
            httpx.Response(200, json=gob_page([gob_item("b")], page=2, total_pages=2)),
        ]
    )

    result = await GetOnBoardSource(client).fetch(QUERY)

    assert [job.external_id for job in result.jobs] == ["a", "b"]
    first, second = (call.request.url.params for call in route.calls)
    assert (first["page"], second["page"]) == ("1", "2")
    assert first["per_page"] == "120"
    assert first["expand"] == '["company"]'


async def test_it_stops_asking_for_pages_once_it_has_enough_jobs(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    route = respx_mock.get(JOBS_URL).respond(
        json=gob_page([gob_item("a"), gob_item("b"), gob_item("c")], total_pages=9)
    )

    result = await GetOnBoardSource(client).fetch(SourceQuery(("programming",), max_jobs=2))

    assert [job.external_id for job in result.jobs] == ["a", "b"]
    assert route.call_count == 1


async def test_a_429_waits_for_retry_after_and_tries_again(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    respx_mock.get(JOBS_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json=gob_page([gob_item("a")])),
        ]
    )
    sleeps = Sleeps()

    result = await GetOnBoardSource(client, sleep=sleeps).fetch(QUERY)

    assert sleeps.waits == [7.0]
    assert len(result.jobs) == 1
    assert result.warnings == []


async def test_a_429_without_retry_after_uses_the_default_wait_and_gives_up_after_two_retries(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    route = respx_mock.get(JOBS_URL).respond(429)
    sleeps = Sleeps()

    result = await GetOnBoardSource(client, sleep=sleeps).fetch(QUERY)

    assert route.call_count == 3  # the first try plus two retries
    assert sleeps.waits == [5.0, 5.0]
    assert result.jobs == []
    assert "limiting requests" in result.warnings[0]


async def test_a_timeout_on_a_later_page_keeps_what_was_already_fetched(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    respx_mock.get(JOBS_URL).mock(
        side_effect=[
            httpx.Response(200, json=gob_page([gob_item("a")], page=1, total_pages=2)),
            httpx.ReadTimeout("slow"),
        ]
    )

    result = await GetOnBoardSource(client).fetch(QUERY)

    assert [job.external_id for job in result.jobs] == ["a"]
    assert result.warnings == ["Get on Board did not answer in time."]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(500), "HTTP 500"),
        (httpx.Response(200, text="<html>maintenance</html>"), "unreadable"),
        (httpx.Response(200, json=["not", "an", "object"]), "unreadable"),
    ],
    ids=["server_error", "not_json", "wrong_shape"],
)
async def test_a_bad_answer_becomes_a_warning_not_an_exception(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient, response: httpx.Response, expected: str
):
    respx_mock.get(JOBS_URL).mock(return_value=response)

    result = await GetOnBoardSource(client).fetch(QUERY)

    assert result.jobs == []
    assert expected in result.warnings[0]


async def test_a_network_error_becomes_a_warning(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    respx_mock.get(JOBS_URL).mock(side_effect=httpx.ConnectError("no route"))

    result = await GetOnBoardSource(client).fetch(QUERY)

    assert result.jobs == []
    assert "ConnectError" in result.warnings[0]


async def test_a_malformed_job_is_skipped_and_counted_without_losing_the_others(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    broken = {"id": "x", "attributes": {"title": "No link"}, "links": {}}
    respx_mock.get(JOBS_URL).respond(json=gob_page([gob_item("ok"), broken, "garbage"]))

    result = await GetOnBoardSource(client).fetch(QUERY)

    assert [job.external_id for job in result.jobs] == ["ok"]
    assert result.warnings == ["Get on Board: 2 malformed job(s) skipped."]


@pytest.mark.parametrize("category", ["../../admin", "programming/../x", "a b", "", "A" * 41])
async def test_a_category_that_could_alter_the_url_path_is_never_requested(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient, category: str
):
    # No routes are registered: any request would raise, so reaching the end proves none was sent.
    result = await GetOnBoardSource(client).fetch(SourceQuery((category,), max_jobs=10))

    assert result.jobs == []
    assert "invalid category" in result.warnings[0]


async def test_the_same_job_in_two_categories_is_returned_once(
    respx_mock: respx.MockRouter, client: httpx.AsyncClient
):
    respx_mock.get(JOBS_URL).respond(json=gob_page([gob_item("same")]))
    respx_mock.get(f"{BASE_URL}/categories/data-science/jobs").respond(
        json=gob_page([gob_item("same")])
    )

    result = await GetOnBoardSource(client).fetch(SourceQuery(("programming", "data-science"), 50))

    assert [job.external_id for job in result.jobs] == ["same"]
