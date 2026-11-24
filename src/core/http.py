"""The one shared HTTP client. Created at startup and closed at shutdown, never per request."""

import httpx

from src.config.constants import HTTP_CONNECT_TIMEOUT_SECONDS, HTTP_TIMEOUT_SECONDS


def make_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        # Every call has a deadline: a slow third party must not hold a tool call hostage.
        timeout=httpx.Timeout(HTTP_TIMEOUT_SECONDS, connect=HTTP_CONNECT_TIMEOUT_SECONDS),
        # A generic client name only: no contact details or user data in outbound headers.
        headers={"User-Agent": "laburo-match"},
    )
