"""Concurrent BFS crawler engine implementing the ``Crawler`` port.

Pipeline per page: robots gate -> per-host rate limit -> concurrency
semaphore -> fetch. Discovered links are normalized, scope- and dedupe-checked,
then enqueued with ``depth + 1``.

Synchronization note: every shared-state mutation happens inside a synchronous
block (no awaits between read and write), so on a single event loop those
blocks are atomic. Workers idle on a wake ``asyncio.Event`` which stays set
until observed, so no wake-up can be lost.
"""

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from sie.domain.errors import (
    CrawlAlreadyRunningError,
    CrawlNotRunningError,
    FetchError,
    InvalidCrawlTargetError,
)
from sie.domain.models.crawl import CrawlPolicy, CrawlStats, CrawlStatus, CrawlTarget
from sie.domain.models.page import FetchedPage
from sie.domain.ports.fetching import Fetcher
from sie.infrastructure.crawling.frontier import LRUSet
from sie.infrastructure.crawling.robots import RobotsGate
from sie.infrastructure.crawling.throttle import PerHostRateLimiter
from sie.infrastructure.crawling.urls import (
    extract_links,
    host_of,
    is_crawlable,
    normalize_url,
    same_site,
)
from sie.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class _PageArrived:
    page: FetchedPage


@dataclass(slots=True)
class _WorkerDone:
    pass


@dataclass
class _RunState:
    policy: CrawlPolicy
    seed_url: str
    frontier: deque[tuple[str, int, str | None]] = field(default_factory=deque)
    visited: LRUSet | None = None
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    out: asyncio.Queue = field(default_factory=asyncio.Queue)
    inflight: int = 0
    stop: bool = False
    discovered: int = 0
    fetched: int = 0
    transport_errors: int = 0
    robots_skipped: int = 0
    started_at: datetime = field(default_factory=_utcnow)
    finished_at: datetime | None = None


class HttpxCrawlerEngine:
    """Single-active-run engine; construct once and inject wherever ``Crawler`` is needed."""

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
    ) -> None:
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._limiter = PerHostRateLimiter(rate_limit_per_host)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_workers = max_concurrency
        self._robots = RobotsGate(fetcher, user_agent=user_agent) if respect_robots_txt else None
        self._follow_cross_origin = follow_cross_origin
        self._visited_cache_size = visited_cache_size
        self._state: _RunState | None = None
        self._last_stats: CrawlStats | None = None

    def crawl(self, target: CrawlTarget, policy: CrawlPolicy) -> AsyncIterator[FetchedPage]:
        """Eagerly validate the request (raises synchronously), return the stream."""
        seed = normalize_url(target.seed_url)
        if not is_crawlable(seed):
            raise InvalidCrawlTargetError(f"not a crawlable HTTP(S) URL: {target.seed_url!r}")
        if self._state is not None:
            raise CrawlAlreadyRunningError("a crawl is already in progress")
        state = _RunState(policy=policy, seed_url=seed, visited=LRUSet(self._visited_cache_size))
        self._enqueue(state, [(seed, 0, None)])
        self._state = state
        return self._stream(state)

    def add_targets(self, targets: Sequence[CrawlTarget]) -> None:
        state = self._state
        if state is None:
            raise CrawlNotRunningError("no crawl is running; call crawl() first")
        candidates = []
        for target in targets:
            url = normalize_url(target.seed_url)
            if is_crawlable(url) and self._in_scope(state, url):
                candidates.append((url, 0, None))
        self._enqueue(state, candidates)

    def get_crawl_stats(self) -> CrawlStats | None:
        state = self._state
        if state is not None:
            return self._snapshot(state)
        return self._last_stats

    async def _stream(self, state: _RunState) -> AsyncIterator[FetchedPage]:
        worker_count = max(1, min(self._max_workers, state.policy.max_pages))
        workers = [asyncio.create_task(self._worker(state)) for _ in range(worker_count)]
        seen_done = 0
        emitted = 0
        draining = False
        try:
            while seen_done < worker_count:
                item = await state.out.get()
                if isinstance(item, _WorkerDone):
                    seen_done += 1
                    continue
                if draining:
                    continue
                emitted += 1
                yield item.page
                if emitted >= state.policy.max_pages:
                    draining = True
                    state.stop = True
                    state.wake.set()
        finally:
            state.stop = True
            state.wake.set()
            await asyncio.gather(*workers, return_exceptions=True)
            state.finished_at = _utcnow()
            self._last_stats = self._snapshot(state)
            self._state = None

    async def _worker(self, state: _RunState) -> None:
        try:
            while True:
                state.wake.clear()
                if state.stop:
                    return
                if state.frontier:
                    url, depth, parent_url = state.frontier.popleft()
                    state.inflight += 1
                    try:
                        await self._process(state, url, depth, parent_url)
                    finally:
                        state.inflight -= 1
                        state.wake.set()
                    continue
                if state.inflight == 0:
                    return
                await state.wake.wait()
        finally:
            state.out.put_nowait(_WorkerDone())

    async def _process(
        self, state: _RunState, url: str, depth: int, parent_url: str | None
    ) -> None:
        minimum_interval: float | None = None
        if self._robots is not None:
            if not await self._robots.allowed(url):
                state.robots_skipped += 1
                logger.debug("robots.txt disallows %s", url)
                return
            minimum_interval = await self._robots.crawl_delay_seconds(url)
        try:
            await self._limiter.acquire(host_of(url), minimum_interval=minimum_interval)
            async with self._semaphore:
                page = await self._fetcher.fetch(url)
        except FetchError as exc:
            state.transport_errors += 1
            logger.warning("fetch failed for %s: %s", url, exc)
            return
        state.fetched += 1
        enriched = replace(page, depth=depth, parent_url=parent_url)
        await state.out.put(_PageArrived(enriched))
        if page.ok and page.is_html and depth < state.policy.depth_limit:
            links = await asyncio.to_thread(extract_links, page.decoded_text(), url)
            candidates = [
                (link, depth + 1, url)
                for link in links
                if is_crawlable(link) and self._in_scope(state, link)
            ]
            self._enqueue(state, candidates)

    def _in_scope(self, state: _RunState, url: str) -> bool:
        return self._follow_cross_origin or same_site(url, state.seed_url)

    @staticmethod
    def _enqueue(state: _RunState, candidates: Sequence[tuple[str, int, str | None]]) -> None:
        assert state.visited is not None
        for url, depth, parent_url in candidates:
            if state.visited.add(url):
                state.frontier.append((url, depth, parent_url))
                state.discovered += 1
        state.wake.set()

    @staticmethod
    def _snapshot(state: _RunState) -> CrawlStats:
        status = CrawlStatus.RUNNING if state.finished_at is None else CrawlStatus.COMPLETED
        return CrawlStats(
            status=status,
            pages_discovered=state.discovered,
            pages_fetched=state.fetched,
            transport_errors=state.transport_errors,
            robots_skipped=state.robots_skipped,
            frontier_size=len(state.frontier),
            started_at=state.started_at,
            finished_at=state.finished_at,
        )
