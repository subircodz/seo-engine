"""Port: persistence for crawl runs and pages."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from sie.domain.models.content import ContentComparison, ContentMetrics, ContentQualityReport
from sie.domain.models.crawl import CrawlPageRecord, CrawlRunRecord, CrawlStatus
from sie.domain.models.diagnosis import DiagnosisResult
from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchKeyword,
)
from sie.domain.models.search_validation import SearchDatasetContent


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

    # ── Search Datasets (Phase 6E) ────────────────────────────────────────────

    async def save_search_dataset(
        self,
        dataset: SearchDataset,
        *,
        keywords: Sequence[SearchKeyword] = (),
        observations: Sequence[RankingObservation] = (),
        competitor_rankings: Sequence[CompetitorRanking] = (),
    ) -> None:
        """Persist a dataset and all its records in one transaction."""
        ...

    async def get_search_dataset(
        self, dataset_id: str
    ) -> tuple[SearchDataset, SearchDatasetContent] | None:
        """Return ``(dataset, content)`` or ``None`` when absent."""
        ...

    async def list_search_datasets(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[int, list[SearchDataset]]:
        """Return ``(total_datasets, datasets)`` ordered by creation descending."""
        ...

    async def delete_search_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset with all records; ``True`` when it existed."""
        ...

    # ── Search Observations (Phase 6I) ─────────────────────────────────────

    async def save_search_observations(
        self,
        dataset_id: str,
        observations: Sequence[RankingObservation],
    ) -> int:
        """Persist ranking observations into an existing dataset.

        Returns the number of rows inserted.  The dataset must already exist;
        callers should validate existence before calling.  No deduplication
        is applied — every observation is stored as a separate row.
        """
        ...

    async def list_search_observations(
        self,
        dataset_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[RankingObservation]]:
        """Return ``(total_count, observations_slice)`` for a dataset.

        Ordered by insertion id (ascending) for deterministic output.
        Returns ``(0, [])`` when the dataset has no observations.
        """
        ...
