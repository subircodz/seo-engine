"""Production post-processing for site-analysis evidence semantics."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from sie.domain.services.site_analysis import SiteAnalysisResult, SiteAnalysisService

__all__ = ["EvidenceAwareSiteAnalysisService"]


class EvidenceAwareSiteAnalysisService:
    """Wrap site analysis and enforce evidence-aware production semantics."""

    def __init__(self, service: SiteAnalysisService) -> None:
        self._service = service

    async def analyze_site(self, *args: Any, **kwargs: Any) -> SiteAnalysisResult:
        result = await self._service.analyze_site(*args, **kwargs)

        ranking = result.rankings
        if ranking is not None and ranking.total_keywords_tracked == 0:
            ranking = replace(ranking, freshness_status="NEVER_COLLECTED")

        aio = result.aio
        if aio is not None and aio.keywords_checked == 0:
            aio = replace(aio, freshness_status="NOT_ASSESSED")

        geo = result.geo
        if geo is not None and geo.keywords_checked == 0:
            geo = replace(geo, freshness_status="NOT_ASSESSED")

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
            if category is not None
            and category.score_status == "ASSESSED"
            and category.overall_score is not None
        ]
        overall = round(sum(assessed) / len(assessed), 1) if assessed else 0.0

        return replace(result, rankings=ranking, aio=aio, geo=geo, overall_score=overall)
