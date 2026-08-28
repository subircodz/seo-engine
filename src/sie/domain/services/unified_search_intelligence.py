"""Unified SEO/AIO/GEO intelligence facade.

This module establishes the product boundary: SEO, AI Overview (AIO), and
Generative Engine Optimization (GEO) are equal first-class search surfaces.
The existing deterministic engines remain independent; this facade combines
their evidence without coupling them to providers or inventing unavailable
data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sie.domain.models.search_aio import AIOverviewResult
from sie.domain.models.search_geo import GEOResult
from sie.domain.models.search_surface import (
    SearchSurface,
    SurfaceAssessment,
    SurfaceStatus,
    UnifiedSearchVisibility,
)
from sie.domain.services.search_intelligence import SearchIntelligenceResult


class UnifiedSearchIntelligenceService:
    """Build the unified visibility view across SEO, AIO, and GEO.

    This is deliberately an orchestration/facade layer.  It performs no I/O,
    provider calls, crawling, or LLM calls.  Its input is already collected
    evidence and its output preserves the distinction between a measured zero
    and a surface that was not assessed.
    """

    def build_visibility(
        self,
        search_result: SearchIntelligenceResult,
        *,
        aio_result: AIOverviewResult | None = None,
        geo_result: GEOResult | None = None,
        generated_at: datetime | None = None,
    ) -> UnifiedSearchVisibility:
        """Create the first-class SEO/AIO/GEO visibility envelope."""
        now = generated_at or datetime.now(UTC)
        assessments = (
            self._seo_assessment(search_result),
            self._aio_assessment(aio_result),
            self._geo_assessment(geo_result),
        )

        assessed_scores = [
            assessment.score
            for assessment in assessments
            if assessment.status == SurfaceStatus.ASSESSED and assessment.score is not None
        ]
        aggregate = round(sum(assessed_scores) / len(assessed_scores), 2) if assessed_scores else None

        return UnifiedSearchVisibility(
            assessments=assessments,
            aggregate_score=aggregate,
            aggregate_methodology=(
                "Arithmetic mean of assessed SEO, AIO, and GEO surface scores only; "
                "unavailable or insufficient surfaces are excluded rather than scored as zero."
            ),
            generated_at=now,
        )

    @staticmethod
    def _seo_assessment(search_result: SearchIntelligenceResult) -> SurfaceAssessment:
        metrics = search_result.analytics.dataset_metrics
        if metrics.total_keywords <= 0:
            return SurfaceAssessment(
                surface=SearchSurface.SEO,
                status=SurfaceStatus.INSUFFICIENT_DATA,
                score=None,
                score_basis="No tracked search keywords were observed.",
                observation_count=0,
                data_source="search analytics",
                limitations=("SEO visibility cannot be scored without ranking observations.",),
            )

        return SurfaceAssessment(
            surface=SearchSurface.SEO,
            status=SurfaceStatus.ASSESSED,
            score=round(metrics.visibility_score * 100.0, 2),
            score_basis="Normalized search visibility score from observed ranking data.",
            observation_count=metrics.total_keywords,
            data_source="search analytics",
        )

    @staticmethod
    def _aio_assessment(aio_result: AIOverviewResult | None) -> SurfaceAssessment:
        if aio_result is None:
            return SurfaceAssessment(
                surface=SearchSurface.AIO,
                status=SurfaceStatus.NOT_ASSESSED,
                score=None,
                score_basis="No AIO observation dataset supplied.",
                observation_count=0,
                data_source="unavailable",
                limitations=("AIO requires collected AI Overview observations.",),
            )

        metrics = aio_result.dataset_metrics
        if metrics.total_ai_overview_observations <= 0:
            return SurfaceAssessment(
                surface=SearchSurface.AIO,
                status=SurfaceStatus.INSUFFICIENT_DATA,
                score=None,
                score_basis="No AI Overview observations were collected.",
                observation_count=0,
                data_source="AIO observations",
                limitations=("No AIO presence was observed, or collection did not produce observations.",),
            )

        return SurfaceAssessment(
            surface=SearchSurface.AIO,
            status=SurfaceStatus.ASSESSED,
            score=round(metrics.target_citation_rate * 100.0, 2),
            score_basis="Target citation rate among observed AI Overview opportunities.",
            observation_count=metrics.total_ai_overview_observations,
            data_source="AIO observations",
        )

    @staticmethod
    def _geo_assessment(geo_result: GEOResult | None) -> SurfaceAssessment:
        if geo_result is None:
            return SurfaceAssessment(
                surface=SearchSurface.GEO,
                status=SurfaceStatus.NOT_ASSESSED,
                score=None,
                score_basis="No GEO observation dataset supplied.",
                observation_count=0,
                data_source="unavailable",
                limitations=("GEO requires observations from a supported generative engine provider.",),
            )

        metrics = geo_result.dataset_metrics
        if metrics.total_observations <= 0:
            return SurfaceAssessment(
                surface=SearchSurface.GEO,
                status=SurfaceStatus.INSUFFICIENT_DATA,
                score=None,
                score_basis="No generative-engine observations were collected.",
                observation_count=0,
                data_source="GEO observations",
                limitations=("GEO visibility cannot be assessed without generative-engine observations.",),
            )

        return SurfaceAssessment(
            surface=SearchSurface.GEO,
            status=SurfaceStatus.ASSESSED,
            score=round(metrics.overall_mention_rate * 100.0, 2),
            score_basis="Target mention rate across observed generative-engine answers.",
            observation_count=metrics.total_observations,
            data_source="GEO observations",
        )


__all__ = ["UnifiedSearchIntelligenceService"]
