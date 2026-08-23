"""HttpxFetcher behaviour against httpx.MockTransport (no network)."""

import httpx
import pytest

from sie.domain.errors import FetchError
from sie.domain.ports.fetching import Fetcher
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher


def _fetcher(handler) -> HttpxFetcher:
    transport = httpx.MockTransport(handler)
    return HttpxFetcher(user_agent="test-agent", client=httpx.AsyncClient(transport=transport))


async def test_fetch_returns_page_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>hi</body></html>",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    fetcher = _fetcher(handler)
    page = await fetcher.fetch("https://example.com/")
    await fetcher.close()

    assert page.ok is True
    assert page.is_html is True
    assert page.final_url == "https://example.com/"
    assert b"hi" in page.content
    assert page.encoding == "utf-8"
    assert page.rendered is False
    assert page.duration_ms >= 0


async def test_follows_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(301, headers={"Location": "https://example.com/final"})
        return httpx.Response(200, text="final page")

    fetcher = _fetcher(handler)
    page = await fetcher.fetch("https://example.com/start")
    await fetcher.close()

    assert page.url == "https://example.com/start"
    assert page.final_url == "https://example.com/final"
    assert page.ok is True


async def test_http_error_status_is_returned_not_raised() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    fetcher = _fetcher(handler)
    page = await fetcher.fetch("https://example.com/")
    await fetcher.close()

    assert page.status_code == 500
    assert page.ok is False


async def test_transport_failure_raises_fetch_error_with_cause() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    fetcher = _fetcher(handler)
    with pytest.raises(FetchError) as excinfo:
        await fetcher.fetch("https://example.com/")
    await fetcher.close()

    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)


async def test_httpx_fetcher_satisfies_fetcher_port() -> None:
    fetcher = HttpxFetcher(user_agent="test-agent")
    try:
        assert isinstance(fetcher, Fetcher)
    finally:
        await fetcher.close()
