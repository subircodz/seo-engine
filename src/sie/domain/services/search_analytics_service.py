"""Search Analytics Service — orchestrates deterministic dataset analysis.

Retrieves a persisted Phase 6E dataset through the existing repository port,
runs the pure ``search_analytics`` engine over its records, and returns a
``SearchAnalyticsResult``.  The service adds no business logic of its own and
performs no I/O beyond the repository call — all computation lives in the
deterministic engine.  No persistence of results (not required by the
current architecture).
"""

from __future__ import annotations

from sie.domain.engines.search_analytics import analyze_search_dataset
from sie.domain.models.search_analytics import SearchAnalyticsResult
from sie.domain.ports.persistence import CrawlRunRepository

__all__ = ["SearchAnalyticsService"]


class SearchAnalyticsService:
    """Analyze persisted search datasets via the repository port."""

    def __init__(self, repository: CrawlRunRepository) -> None:
        self._repo = repository

    async def analyze_dataset(self, dataset_id: str) -> SearchAnalyticsResult | None:
        """Return the analytics result for ``dataset_id``, or ``None`` if absent."""
        stored = await self._repo.get_search_dataset(dataset_id)
        if stored is None:
            return None
        dataset, content = stored
        return analyze_search_dataset(
            dataset,
            content.observations,
            content.competitor_rankings,
        )
