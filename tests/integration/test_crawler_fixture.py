"""Full crawler engine pipeline against a fixture site (no network)."""

import asyncio

import httpx
import pytest

from sie.domain.models.crawl import CrawlPolicy, CrawlTarget
from sie.infrastructure.crawling.engine import HttpxCrawlerEngine
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher

ROBOTS = """\
User-agent: *
Disallow: /private/
"""

SITE = {
    "/": (
        """
        <html><body>
        <a href="/a">A</a>
        <a href="/b">B</a>
        <a href="https://other.test/x">external</a>
        <a href="/a">dup A</a>
        <a href="#section">fragment only</a>
        <a href="/private/hidden">secret</a>
        </body></html>
        """,
        "text/html",
    ),
    "/a": ('<html><body><a href="/deep1">deep</a></body></html>', "text/html"),
    "/b": ("<html><body>404 page</body></html>", "text/html"),
    "/deep1": ('<html><body><a href="/deep2">deeper</a></body></html>', "text/html"),
    "/deep2": ("<html>leaf</html>", "text/html"),
    "/private/hidden": ("<html>secret</html>", "text/html"),
}


def handler_factory(counts: dict[str, int]):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        counts[path] = counts.get(path, 0) + 1
        if path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        entry = SITE.get(path)
        if entry is None:
            return httpx.Response(404, text="missing", headers={"Content-Type": "text/html"})
        body, ctype = entry
        if path == "/b":
            return httpx.Response(404, content=body.encode(), headers={"Content-Type": ctype})
        return httpx.Response(200, content=body.encode(), headers={"Content-Type": ctype})

    return handler


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep fixture-site tests independent of the machine's DNS configuration."""

    def getaddrinfo(hostname, *args, **kwargs):
        if hostname in {"example.test", "other.test"}:
            return [(2, 1, 6, "", ("93.184.216.34", 0))]
        raise AssertionError(f"unexpected DNS lookup in crawler fixture: {hostname}")

    monkeypatch.setattr("sie.domain.security.ssrf.socket.getaddrinfo", getaddrinfo)


@pytest.fixture
async def run_crawl():
    """Factory returning (pages, stats, request_counts) for a given policy."""

    async def _run(policy: CrawlPolicy) -> tuple[list, object, dict[str, int]]:
        counts: dict[str, int] = {}
        fetcher = HttpxFetcher(
            user_agent="test-bot",
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler_factory(counts))),
        )
        try:
            engine = HttpxCrawlerEngine(
                fetcher=fetcher,
                user_agent="test-bot",
                rate_limit_per_host=10_000,
                respect_robots_txt=True,
            )
            pages = []
            async for page in engine.crawl(CrawlTarget(seed_url="https://example.test/"), policy):
                pages.append(page)
            await asyncio.sleep(0.05)
            return pages, engine.get_crawl_stats(), counts
        finally:
            await fetcher.close()

    return _run


async def test_bfs_dedup_robots_and_error_pages(run_crawl):
    pages, _stats, counts = await run_crawl(
        CrawlPolicy(max_pages=50, depth_limit=5, rate_limit_per_host=10_000)
    )

    urls = {p.url for p in pages}
    assert urls == {
        "https://example.test/",
        "https://example.test/a",
        "https://example.test/b",
        "https://example.test/deep1",
        "https://example.test/deep2",
    }

    by_url = {p.url: p for p in pages}
    assert by_url["https://example.test/b"].status_code == 404
    assert by_url["https://example.test/"].depth == 0
    assert by_url["https://example.test/a"].depth == 1
    assert by_url["https://example.test/a"].parent_url == "https://example.test/"

    assert counts.get("/a") == 1
    assert counts.get("/private/hidden") is None


async def test_depth_limit_enforced(run_crawl):
    pages, _, _ = await run_crawl(CrawlPolicy(max_pages=50, depth_limit=2))
    urls = {p.url for p in pages}
    assert "https://example.test/deep1" in urls
    assert "https://example.test/deep2" not in urls


async def test_cross_origin_blocked_by_default(run_crawl):
    pages, _, counts = await run_crawl(CrawlPolicy(max_pages=50, depth_limit=1))
    assert all("other.test" not in p.url for p in pages)
    assert counts.get("/x", 0) == 0


async def test_max_pages_cap_stops_stream(run_crawl):
    pages, stats, _ = await run_crawl(CrawlPolicy(max_pages=2, depth_limit=5))
    assert len(pages) == 2
    assert stats.status.value == "completed"


async def test_stats_snapshot_after_completion(run_crawl):
    _, stats, _ = await run_crawl(CrawlPolicy(max_pages=50, depth_limit=5))
    assert stats.pages_fetched == 5
    assert stats.pages_discovered == 6
    assert stats.transport_errors == 0
    assert stats.robots_skipped == 1
    assert stats.frontier_size == 0
    assert stats.finished_at is not None


async def test_engine_satisfies_crawler_port(run_crawl):
    from sie.domain.ports.crawling import Crawler

    counts: dict[str, int] = {}
    fetcher = HttpxFetcher(
        user_agent="test-bot",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler_factory(counts))),
    )
    try:
        engine = HttpxCrawlerEngine(fetcher=fetcher, user_agent="test-bot")
        assert isinstance(engine, Crawler)
    finally:
        await fetcher.close()
