"""Real-world integration test against https://power.win.

Marked ``network``: run with ``pytest -m network``. Skipped automatically when
the host is unreachable so the rest of the suite never blocks on connectivity.
"""

import asyncio
import os

import httpx
import pytest

from sie.domain.models.crawl import CrawlPolicy, CrawlTarget
from sie.infrastructure.crawling.engine import HttpxCrawlerEngine
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher
from sie.infrastructure.fetching.retrying_fetcher import RetryingFetcher

TARGET = "https://power.win"
MAX_PAGES = int(os.environ.get("SIE_TEST_MAX_PAGES", "50"))
TIMEOUT = 60.0

pytestmark = pytest.mark.network


@pytest.fixture
async def fetcher():
    inner = HttpxFetcher(user_agent="SieCrawler/1.0", timeout_seconds=30.0)
    retrying = RetryingFetcher(inner, max_retries=2, base_delay_seconds=1.0)
    yield retrying
    await retrying.close()


async def _reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.head(TARGET, follow_redirects=True)
            return response.status_code < 500
    except httpx.HTTPError:
        return False


@pytest.fixture
async def crawl_result(fetcher):
    if not await _reachable():
        pytest.skip(f"{TARGET} unreachable; skipping real-network test")

    engine = HttpxCrawlerEngine(
        fetcher=fetcher,
        user_agent="SieCrawler/1.0",
        max_concurrency=5,
        rate_limit_per_host=4.0,
        respect_robots_txt=True,
    )
    pages = []
    policy = CrawlPolicy(
        max_pages=MAX_PAGES,
        depth_limit=3,
        rate_limit_per_host=4.0,
        respect_robots_txt=True,
    )
    async for page in engine.crawl(CrawlTarget(seed_url=TARGET), policy):
        pages.append(page)
    await asyncio.sleep(0.1)
    return pages, engine.get_crawl_stats()


async def test_power_win_crawl_returns_pages(crawl_result):
    pages, stats = crawl_result

    assert len(pages) > 0, "no pages fetched from power.win"
    assert stats.pages_fetched == len(pages)

    ok_pages = [p for p in pages if p.ok]
    assert len(ok_pages) > 0, f"all {len(pages)} requests failed"


async def test_power_win_respects_scope(crawl_result):
    pages, _ = crawl_result
    for page in pages:
        assert "power.win" in page.url or "www.power.win" in page.url


async def test_power_win_stores_provenance(crawl_result):
    pages, _ = crawl_result
    seed = [p for p in pages if p.depth == 0]
    assert seed, "seed page missing from results"
    assert seed[0].url.rstrip("/") == TARGET
