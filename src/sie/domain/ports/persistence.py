"""Port: persistence for crawl runs and pages."""

from datetime import datetime
from typing import Protocol

from sie.domain.models.content import ContentComparison, ContentMetrics, ContentQualityReport
from sie.domain.models.crawl import CrawlPageRecord, CrawlRunRecord, CrawlStatus
from sie.domain.models.diagnosis import DiagnosisResult


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

    # ── Content Intelligence ──────────────────────────────────────────────────

    async def save_content_metrics(self, run_id: str, metrics: list[ContentMetrics]) -> None: ...

    async def get_content_metrics(self, run_id: str) -> list[ContentMetrics]: ...

    async def save_content_comparisons(
        self, run_id: str, comparisons: list[ContentComparison]
    ) -> None: ...

    async def get_content_comparisons(self, run_id: str) -> list[ContentComparison]: ...

    async def save_quality_report(self, run_id: str, report: ContentQualityReport) -> None: ...

    async def get_quality_report(self, run_id: str) -> ContentQualityReport | None: ...

    # ── SEO Diagnosis ─────────────────────────────────────────────────────────

    async def save_diagnosis_result(self, run_id: str, result: DiagnosisResult) -> None: ...

    async def get_diagnosis_result(self, run_id: str) -> DiagnosisResult | None: ...

    # ── Intelligence Reports (Phase 5C) ───────────────────────────────────────

    async def save_intelligence_report(self, run_id: str, report: object) -> None: ...

    async def get_intelligence_report(self, intelligence_id: str) -> object | None: ...

    async def get_intelligence_report_by_run_id(self, run_id: str) -> object | None: ...
