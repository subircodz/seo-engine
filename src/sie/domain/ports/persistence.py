"""Port: persistence for crawl runs and pages."""

from datetime import datetime
from typing import Protocol

from sie.domain.models.crawl import CrawlPageRecord, CrawlRunRecord, CrawlStatus


class CrawlRunRepository(Protocol):
    """Storage contract implemented by infrastructure (SQLAlchemy today)."""

    async def create_run(self, run: CrawlRunRecord) -> None: ...

    async def finish_run(
        self,
        run_id: str,
        *,
        status: CrawlStatus,
        completed_at: datetime,
        error: str | None = None,
        total_pages: int = 0,
        error_count: int = 0,
    ) -> None: ...

    async def get_run(self, run_id: str) -> CrawlRunRecord | None: ...

    async def add_page(self, run_id: str, page: CrawlPageRecord) -> None: ...

    async def list_pages(
        self, run_id: str, *, limit: int, offset: int
    ) -> tuple[int, list[CrawlPageRecord]]:
        """Return ``(total_pages_for_run, page_slice)`` ordered by insertion."""
        ...

    async def list_runs(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[int, list[CrawlRunRecord]]:
        """Return ``(total_runs, runs)`` ordered by start time descending."""
        ...
