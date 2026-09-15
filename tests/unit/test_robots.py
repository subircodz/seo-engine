"""robots.txt compliance gate behaviour."""

import httpx
import pytest

from sie.infrastructure.crawling.robots import RobotsGate
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher


def _fetcher(handler) -> HttpxFetcher:
    return HttpxFetcher(
        user_agent="test-bot",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep MockTransport robots tests independent of external DNS."""

    def getaddrinfo(hostname, *args, **kwargs):
        if hostname.endswith(".example") or hostname == "example.com":
            return [(2, 1, 6, "", ("93.184.216.34", 0))]
        raise AssertionError(f"unexpected DNS lookup in robots test: {hostname}")

    monkeypatch.setattr("sie.domain.security.ssrf.socket.getaddrinfo", getaddrinfo)


ROBOTS_DISALLOW_PRIVATE = """\
User-agent: *
Disallow: /private/
"""

ROBOTS_WITH_DELAY = """\
User-agent: *
Crawl-delay: 3
"""


async def test_allowed_when_robots_disallow_matches_path():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_DISALLOW_PRIVATE)
        return httpx.Response(200, text="ok")

    gate = RobotsGate(_fetcher(handler), user_agent="test-bot")
    assert await gate.allowed("https://example.com/allowed") is True
    assert await gate.allowed("https://example.com/private/secret") is False


async def test_robots_404_allows_everything():
    def handler(request):
        return httpx.Response(404)

    gate = RobotsGate(_fetcher(handler), user_agent="test-bot")
    assert await gate.allowed("https://example.com/anything") is True


async def test_robots_500_disallows_everything():
    def handler(request):
        return httpx.Response(500)

    gate = RobotsGate(_fetcher(handler), user_agent="test-bot")
    assert await gate.allowed("https://example.com/ok") is False


async def test_crawl_delay_parsed():
    def handler(request):
        return httpx.Response(200, text=ROBOTS_WITH_DELAY)

    gate = RobotsGate(_fetcher(handler), user_agent="test-bot")
    delay = await gate.crawl_delay_seconds("https://example.com/something")
    assert delay == pytest.approx(3.0)


async def test_robots_cache_is_bounded():
    def handler(request):
        return httpx.Response(404)

    gate = RobotsGate(_fetcher(handler), user_agent="test-bot", max_cache_entries=2)
    assert await gate.allowed("https://one.example/") is True
    assert await gate.allowed("https://two.example/") is True
    assert await gate.allowed("https://three.example/") is True

    assert len(gate._entries) == 2
    assert "https://one.example" not in gate._entries
    assert "https://two.example" in gate._entries
    assert "https://three.example" in gate._entries


async def test_robots_cache_preserves_port_as_part_of_origin():
    requests: list[str] = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(404)

    gate = RobotsGate(_fetcher(handler), user_agent="test-bot")
    assert await gate.allowed("https://example.com:8443/page") is True
    assert await gate.allowed("https://example.com:9443/page") is True

    assert requests == [
        "https://example.com:8443/robots.txt",
        "https://example.com:9443/robots.txt",
    ]
