"""Unified SEO/AIO/GEO visibility API.

This endpoint is the product-level search-intelligence view.  SEO, AIO and GEO
remain first-class surfaces, while the existing site-analysis endpoint remains
backward compatible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from sie.api.auth import api_key_auth
from sie.domain.models.search_surface import SearchSurface, SurfaceAssessment, SurfaceStatus, UnifiedSearchVisibility

router = APIRouter(
    prefix="/api/search-visibility",
    tags=["search-visibility"],
    dependencies=[Depends(api_key_auth)],
)


class UnifiedVisibilityResponse(BaseModel):
    domain: str
    visibility: dict[str, Any]
    recommendations: list[dict[str, Any]]
    analyzed_at: str


def _assessment(surface: SearchSurface, breakdown, source: str) -> SurfaceAssessment:
    if breakdown is None:
        return SurfaceAssessment(
            surface=surface,
            status=SurfaceStatus.NOT_ASSESSED,
            score=None,
            score_basis="No assessment was produced for this search surface.",
            observation_count=0,
            data_source=source,
            limitations=("The surface was not assessed during this analysis.",),
        )

    status_text = str(breakdown.score_status).upper().replace(" ", "_")
    status_map = {
        "ASSESSED": SurfaceStatus.ASSESSED,
        "NOT_ASSESSED": SurfaceStatus.NOT_ASSESSED,
        "INSUFFICIENT_DATA": SurfaceStatus.INSUFFICIENT_DATA,
        "COLLECTION_FAILED": SurfaceStatus.COLLECTION_FAILED,
        "STALE": SurfaceStatus.STALE,
    }
    status = status_map.get(status_text, SurfaceStatus.NOT_ASSESSED)
    score = breakdown.overall_score if status == SurfaceStatus.ASSESSED else None
    return SurfaceAssessment(
        surface=surface,
        status=status,
        score=score,
        score_basis=breakdown.scoring_methodology,
        observation_count=breakdown.sample_size,
        data_source=breakdown.data_source or source,
        observed_at=(
            datetime.fromisoformat(breakdown.observation_date.replace("Z", "+00:00"))
            if breakdown.observation_date
            else None
        ),
        limitations=tuple(breakdown.limitations),
    )


def _seo_assessment(result) -> SurfaceAssessment:
    """Build SEO as the shared traditional-search surface from its assessed categories."""
    categories = (
        result.technical_breakdown,
        result.content_breakdown,
        result.ranking_breakdown,
        result.architecture_breakdown,
    )
    assessed = [
        category for category in categories
        if category is not None
        and category.score_status == "ASSESSED"
        and category.overall_score is not None
    ]
    if not assessed:
        return SurfaceAssessment(
            surface=SearchSurface.SEO,
            status=SurfaceStatus.INSUFFICIENT_DATA,
            score=None,
            score_basis="No assessed traditional-search SEO categories are available.",
            observation_count=0,
            data_source="site analysis",
            limitations=("SEO visibility requires assessed technical, content, ranking, or architecture evidence.",),
        )
    return SurfaceAssessment(
        surface=SearchSurface.SEO,
        status=SurfaceStatus.ASSESSED,
        score=round(sum(c.overall_score for c in assessed) / len(assessed), 2),
        score_basis="Arithmetic mean of assessed technical, content, ranking, and architecture SEO categories.",
        observation_count=sum(c.sample_size for c in assessed),
        data_source="site analysis",
        limitations=tuple(sorted({limit for c in assessed for limit in c.limitations})),
    )


def _serialize_recommendation(rec) -> dict[str, Any]:
    return {
        "category": rec.category.value,
        "priority": rec.priority.value,
        "title": rec.title,
        "description": rec.description,
        "confidence": rec.confidence,
        "affected_keywords": list(rec.affected_keywords),
        "affected_urls": list(rec.affected_urls),
        "supporting_metrics": rec.supporting_metrics,
    }


@router.post("/analyze", response_model=UnifiedVisibilityResponse)
async def analyze_search_visibility(body: dict[str, Any], request: Request) -> UnifiedVisibilityResponse:
    """Run the existing site analysis and expose its SEO/AIO/GEO result as one envelope."""
    result = await request.app.state.site_analysis_service.analyze_site(
        domain=body.get("domain", ""),
        max_pages=body.get("max_pages", 100),
        max_keywords=body.get("max_keywords", 50),
        country=body.get("country", "us"),
        target_countries=body.get("target_countries"),
        device=body.get("device", "desktop"),
        competitors=body.get("competitors"),
        deep_aio=body.get("deep_aio", True),
        deep_geo=body.get("deep_geo", True),
    )

    assessments = (
        _seo_assessment(result),
        _assessment(SearchSurface.AIO, result.aio_breakdown, "AIO observations"),
        _assessment(SearchSurface.GEO, result.geo_breakdown, "GEO observations"),
    )
    assessed_scores = [a.score for a in assessments if a.status == SurfaceStatus.ASSESSED and a.score is not None]
    aggregate = round(sum(assessed_scores) / len(assessed_scores), 2) if assessed_scores else None
    visibility = UnifiedSearchVisibility(
        assessments=assessments,
        aggregate_score=aggregate,
        aggregate_methodology=(
            "Arithmetic mean of assessed SEO, AIO and GEO surfaces only. "
            "Unavailable or insufficient surfaces are excluded rather than treated as zero."
        ),
        generated_at=datetime.now(UTC),
    )

    return UnifiedVisibilityResponse(
        domain=result.domain,
        visibility={
            "aggregate_score": visibility.aggregate_score,
            "aggregate_methodology": visibility.aggregate_methodology,
            "assessed_surfaces": [a.surface.value for a in visibility.assessed_surfaces],
            "unavailable_surfaces": [a.surface.value for a in visibility.unavailable_surfaces],
            "surfaces": [
                {
                    "surface": a.surface.value,
                    "status": a.status.value,
                    "score": a.score,
                    "score_basis": a.score_basis,
                    "observation_count": a.observation_count,
                    "data_source": a.data_source,
                    "observed_at": a.observed_at.isoformat() if a.observed_at else None,
                    "limitations": list(a.limitations),
                }
                for a in visibility.assessments
            ],
        },
        recommendations=[_serialize_recommendation(r) for r in result.recommendations],
        analyzed_at=result.analyzed_at.isoformat(),
    )
