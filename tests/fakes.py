"""Shared test fakes (importable without fixtures via tests.fakes)."""

import asyncio
from collections import defaultdict
from dataclasses import replace

from sie.domain.models.crawl import CrawlPageRecord, CrawlRunRecord, CrawlStats


class FakeCrawler:
    """Deterministic stand-in for ``Crawler`` port.

    * ``pages`` is yielded in order on each ``crawl()`` call.
    * ``stall`` blocks stream entry until ``stall.set()`` (or is ignored when
      ``None``).
    """

    def __init__(self, pages=(), *, stall: asyncio.Event | None = None):
        self._pages = list(pages)
        self._stall = stall
        self.received_targets: list = []
        self.stats: CrawlStats | None = None

    def crawl(self, target, policy):
        self.received_targets.append((target, policy))
        return self._stream()

    async def _stream(self):
        for page in self._pages:
            if self._stall is not None:
                await self._stall.wait()
            yield page

    def add_targets(self, targets):
        self.received_targets.extend(targets)

    def get_crawl_stats(self):
        return self.stats


class FailingCrawler:
    """Raises on the first ``crawl()`` iteration."""

    def __init__(self, exception: Exception):
        self._exc = exception

    async def _stream(self):
        raise self._exc
        yield  # make it an async generator

    def crawl(self, target, policy):
        return self._stream()

    def add_targets(self, targets):
        pass

    def get_crawl_stats(self):
        return None


class InMemoryCrawlRunRepository:
    def __init__(self):
        self.runs: dict[str, CrawlRunRecord] = {}
        self.pages: dict[str, list[CrawlPageRecord]] = defaultdict(list)

    async def create_run(self, run: CrawlRunRecord) -> None:
        self.runs[run.id] = run

    async def finish_run(
        self, run_id, *, status, completed_at, error=None, total_pages=0, error_count=0
    ):
        run = self.runs.get(run_id)
        if run is None:
            return
        self.runs[run_id] = replace(
            run,
            status=status,
            completed_at=completed_at,
            error=error,
            total_pages=total_pages,
            error_count=error_count,
        )

    async def get_run(self, run_id: str) -> CrawlRunRecord | None:
        return self.runs.get(run_id)

    async def add_page(self, run_id: str, page: CrawlPageRecord) -> None:
        if run_id in self.runs:
            self.pages[run_id].append(page)

    async def list_pages(self, run_id, *, limit, offset):
        items = self.pages.get(run_id, [])
        return len(items), items[offset : offset + limit]

    async def list_runs(self, *, limit=50, offset=0):
        runs = sorted(self.runs.values(), key=lambda r: r.started_at, reverse=True)
        return len(runs), runs[offset : offset + limit]
