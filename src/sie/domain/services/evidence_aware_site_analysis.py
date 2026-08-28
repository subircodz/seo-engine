"""Production post-processing for site-analysis evidence semantics."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from sie.domain.services.site_analysis import SiteAnalysisResult, SiteAnalysisService

__all__ = ["EvidenceAwareSiteAnalysisService"]


class EvidenceAwareSiteAnalysisService:
    """Wrap ``SiteAnalysisService`` and prevent unavailable dimensions from penalizing scores.

    The legacy service keeps numeric compatibility fields. This wrapper makes
    the production result evidence-aware by recomputing the overall score only
    from categories whose breakdown is actually assessed.
    """

    def __init__(self, service: SiteAnalysisService) -> None:
        self._service = service

    async def analyze_site(self, *args: Any, **kwargs: Any) -> SiteAnalysisResult:
        result = await self._service.analyze_site(*args, **kwargs)
        categories = (
            result.technical_breakdown,
            result.content_breakdown,
            result.ranking_breakdown,
            result.architecture_breakdown,
            result.aio_breakdown,
            result.geo_breakdown,
        )
        assessed = [
            category.overall_score
            for category in categories
            if category is not None and category.score_status == "ASSESSED" and category.overall_score is not None
        ]
        if not assessed:
            overall = 0.0
        else:
            overall = round(sum(assessed) / len(assessed), 1)
        return replace(result, overall_score=overall)
