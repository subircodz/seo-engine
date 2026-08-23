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
