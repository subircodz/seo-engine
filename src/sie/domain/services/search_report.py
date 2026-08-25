"""Consolidated Intelligence Reporting Service (Phase 8).

Orchestrates the report generation engine.
"""

from __future__ import annotations

from sie.domain.engines.search_report import generate_intelligence_report
from sie.domain.models.search_report import IntelligenceReport

__all__ = ["ReportingService"]


class ReportingService:
    """Service for consolidated intelligence report generation."""

    def generate_report(self, dataset_id: str, **kwargs) -> IntelligenceReport:
        """Generate a consolidated intelligence report."""
        return generate_intelligence_report(dataset_id, **kwargs)
