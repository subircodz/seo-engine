"""Performance Intelligence Service (Phase 8).

Orchestrates the Performance Intelligence engine through the
deterministic analysis pipeline.  No business logic — pure delegation.
"""

from __future__ import annotations

from sie.domain.engines.search_performance import (
    analyze_dataset_performance,
    analyze_page_performance,
)
from sie.domain.models.search_performance import (
    PerformanceDatasetMetrics,
    PerformanceResult,
)

__all__ = ["PerformanceIntelligenceService"]


class PerformanceIntelligenceService:
    """Service for page and dataset performance analysis."""

    def analyze_page(self, **kwargs) -> PerformanceResult:
        """Analyze a single page's performance characteristics."""
        return analyze_page_performance(**kwargs)

    def analyze_dataset(
        self, dataset_id: str, pages: tuple[dict, ...]
    ) -> PerformanceDatasetMetrics:
        """Analyze performance across a dataset of pages."""
        return analyze_dataset_performance(dataset_id, pages)
