"""HttpxFetcher behaviour against httpx.MockTransport (no network)."""

import httpx
import pytest

from sie.domain.errors import FetchError
from sie.domain.ports.fetching import Fetcher
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher


def _fetcher(handler, **kwargs) -> HttpxFetcher:
    transport = httpx.MockTransport(handler)
    return HttpxFetcher(
        user_agent="test-agent",
        client=httpx.AsyncClient(transport=transport),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep MockTransport tests independent of the machine's DNS configuration."""

    def getaddrinfo(hostname, *args, **kwargs):
        if hostname == "example.com":
            return [(2, 1, 6, "", ("93.184.216.34", 0))]
        raise AssertionError(f"unexpected DNS lookup in MockTransport test: {hostname}")

    monkeypatch.setattr("sie.domain.security.ssrf.socket.getaddrinfo", getaddrinfo)


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


async def test_redirect_to_private_ip_is_blocked_before_request() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/internal"},
            request=request,
        )

    fetcher = _fetcher(handler)
    with pytest.raises(FetchError, match="blocked redirect"):
        await fetcher.fetch("https://example.com/start")
    await fetcher.close()

    assert requested == ["https://example.com/start"]


async def test_dns_resolution_to_private_ip_is_blocked_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    def getaddrinfo(hostname, *args, **kwargs):
        return [(2, 1, 6, "", ("10.0.0.5", 0))]

    monkeypatch.setattr("sie.domain.security.ssrf.socket.getaddrinfo", getaddrinfo)

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, text="must not be requested", request=request)

    fetcher = _fetcher(handler)
    with pytest.raises(FetchError, match="private/internal IP"):
        await fetcher.fetch("https://attacker.example/")
    await fetcher.close()

    assert requested == []


async def test_safe_relative_redirect_is_followed() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/final"}, request=request)
        return httpx.Response(200, text="final page", request=request)

    fetcher = _fetcher(handler)
    page = await fetcher.fetch("https://example.com/start")
    await fetcher.close()

    assert requested == ["https://example.com/start", "https://example.com/final"]
    assert page.final_url == "https://example.com/final"


async def test_redirect_limit_is_enforced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/loop"}, request=request)

    fetcher = _fetcher(handler, max_redirects=2)
    with pytest.raises(FetchError, match="maximum redirects"):
        await fetcher.fetch("https://example.com/start")
    await fetcher.close()


async def test_http_error_status_is_returned_not_raised() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    fetcher = _fetcher(handler)
    page = await fetcher.fetch("https://example.com/")
    await fetcher.close()

    assert page.status_code == 500
    assert page.ok is False


async def test_response_body_size_is_enforced_for_streamed_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"0123456789", request=request)

    fetcher = _fetcher(handler, max_response_bytes=5)
    with pytest.raises(FetchError, match="response body exceeds maximum size"):
        await fetcher.fetch("https://example.com/")
    await fetcher.close()


async def test_response_body_size_is_rejected_from_content_length() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"0123456789",
            headers={"Content-Length": "10"},
            request=request,
        )

    fetcher = _fetcher(handler, max_response_bytes=5)
    with pytest.raises(FetchError, match="response body exceeds maximum size"):
        await fetcher.fetch("https://example.com/")
    await fetcher.close()


async def test_invalid_response_size_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_response_bytes must be positive"):
        _fetcher(lambda request: httpx.Response(200), max_response_bytes=0)


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
