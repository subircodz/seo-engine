"""Cloudflare bypass crawler engine wrapper.

This wrapper uses CloudflareBypassFetcher to enable Cloudflare bypass
for the standard HttpxCrawlerEngine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sie.domain.ports.fetching import Fetcher
from sie.infrastructure.crawling.engine import HttpxCrawlerEngine
from sie.infrastructure.fetching.cloudflare_bypass_fetcher import CloudflareBypassFetcher
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher

if TYPE_CHECKING:
    pass


class CloudflareBypassCrawlerEngine:
    """Crawler engine that wraps HttpxCrawlerEngine with Cloudflare bypass capability.

    This wrapper creates a CloudflareBypassFetcher that wraps the base fetcher,
    allowing the standard HttpxCrawlerEngine to bypass Cloudflare challenges
    automatically via session hijacking.
    """

    def __init__(
        self,
        *,
        fetcher: Fetcher,
        user_agent: str,
        max_concurrency: int = 10,
        rate_limit_per_host: float = 1.0,
        respect_robots_txt: bool = True,
        follow_cross_origin: bool = False,
        visited_cache_size: int = 100_000,
        # Cloudflare bypass options
        enable_bypass: bool = True,
        browser_timeout_seconds: float = 30.0,
        browser_wait_seconds: float = 10.0,
        headless: bool = True,
        max_browser_retries: int = 2,
    ) -> None:
        # Create base fetcher (will be wrapped)
        if not isinstance(fetcher, HttpxFetcher):
            # Create default fetcher if not HttpxFetcher
            fetcher = HttpxFetcher(
                user_agent=user_agent,
                timeout_seconds=30.0,
                connect_timeout_seconds=5.0,
                read_timeout_seconds=20.0,
                write_timeout_seconds=10.0,
                pool_timeout_seconds=5.0,
                allow_localhost=False,
            )

        # Create bypass fetcher
        if enable_bypass:
            bypass_fetcher = CloudflareBypassFetcher(
                base_fetcher=fetcher,
                browser_timeout_seconds=browser_timeout_seconds,
                browser_wait_seconds=browser_wait_seconds,
                headless=headless,
                max_browser_retries=max_browser_retries,
            )
            crawler_fetcher = bypass_fetcher
        else:
            crawler_fetcher = fetcher

        # Create standard crawler engine with bypass fetcher
        self._engine = HttpxCrawlerEngine(
            fetcher=crawler_fetcher,
            user_agent=user_agent,
            max_concurrency=max_concurrency,
            rate_limit_per_host=rate_limit_per_host,
            respect_robots_txt=respect_robots_txt,
            follow_cross_origin=follow_cross_origin,
            visited_cache_size=visited_cache_size,
        )

        self._enable_bypass = enable_bypass
        self._bypass_fetcher = bypass_fetcher if enable_bypass else None

    def crawl(self, target, policy):
        """Crawl target with policy, yielding fetched pages."""
        return self._engine.crawl(target, policy)

    def add_targets(self, targets):
        """Add additional targets to an ongoing crawl."""
        return self._engine.add_targets(targets)

    def get_crawl_stats(self):
        """Get crawl statistics."""
        return self._engine.get_crawl_stats()

    async def close(self) -> None:
        """Close the engine and release resources."""
        if self._bypass_fetcher:
            await self._bypass_fetcher.close()
        # The base engine doesn't have a close method, but the fetcher does
        pass
