"""Site Analysis API endpoints — unified website intelligence."""

from __future__ import annotations

import io
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sie.api.auth import api_key_auth
from sie.domain.renderers.pdf_renderer import PDFGenerationError, PDFRenderer
from sie.domain.services.site_analysis import SiteAnalysisResult, create_site_analysis_service

router = APIRouter(
    prefix="/api/site",
    tags=["site-analysis"],
    dependencies=[Depends(api_key_auth)],
)


class SiteAnalyzeRequest(BaseModel):
    """Request to analyze a website."""
    domain: str = Field(..., description="Domain to analyze (e.g., example.com or https://example.com)")
    max_pages: int = Field(default=100, ge=1, le=500, description="Maximum pages to crawl")
    max_keywords: int = Field(default=50, ge=1, le=200, description="Maximum keywords to check rankings for")
    country: str = Field(default="us", description="Country code for search (e.g., us, gb, de)")
    device: str = Field(default="desktop", description="Device type: desktop or mobile")
    competitors: list[str] = Field(default=[], max_length=5, description="Competitor domains to track")
    deep_aio: bool = Field(default=True, description="Enable AI Overview analysis")
    deep_geo: bool = Field(default=True, description="Enable Generative Engine analysis")


class SiteAnalyzeResponse(BaseModel):
    """Response from site analysis."""
    domain: str
    analyzed_at: str
    crawl_run_id: str | None

    # Overall scores (0-100)
    overall_score: float
    technical_score: float
    content_score: float
    ranking_score: float
    architecture_score: float
    aio_score: float
    geo_score: float

    # Rankings summary
    rankings: dict | None = None
    technical: dict | None = None
    content: dict | None = None
    architecture: dict | None = None
    aio: dict | None = None
    geo: dict | None = None

    # Prioritized recommendations
    recommendations: list[dict]


def _site_analysis_service(request: Request):
    """Get site analysis service from app state."""
    from sie.domain.services.site_analysis import create_site_analysis_service
    return create_site_analysis_service(
        crawl_service=request.app.state.crawl_service,
        audit_service=request.app.state.audit_service,
        content_service=request.app.state.content_service,
        search_provider=request.app.state.search_provider,
        repository=request.app.state.repository,
    )


def _serialize_recommendation(rec) -> dict:
    return {
        "category": rec.category.value,
        "priority": rec.priority.value,
        "title": rec.title,
        "description": rec.description,
        "affected_keywords": list(rec.affected_keywords),
        "affected_urls": list(rec.affected_urls),
        "supporting_metrics": rec.supporting_metrics,
        "confidence": rec.confidence,
    }


def _serialize_rankings(rankings) -> dict | None:
    if not rankings:
        return None
    return {
        "domain": rankings.domain,
        "total_keywords_tracked": rankings.total_keywords_tracked,
        "keywords_in_top_3": rankings.keywords_in_top_3,
        "keywords_in_top_10": rankings.keywords_in_top_10,
        "keywords_in_top_20": rankings.keywords_in_top_20,
        "keywords_not_ranking": rankings.keywords_not_ranking,
        "visibility_score": rankings.visibility_score,
        "estimated_monthly_traffic": rankings.estimated_monthly_traffic,
        "top_keywords": rankings.top_keywords,
        "collected_at": rankings.collected_at.isoformat() if rankings.collected_at else None,
    }


def _serialize_technical(tech) -> dict | None:
    if not tech:
        return None
    return {
        "pages_crawled": tech.pages_crawled,
        "critical_issues": tech.critical_issues,
        "warning_issues": tech.warning_issues,
        "info_issues": tech.info_issues,
        "indexable_pages": tech.indexable_pages,
        "non_indexable_pages": tech.non_indexable_pages,
        "avg_load_time_ms": tech.avg_load_time_ms,
        "core_web_vitals_pass": tech.core_web_vitals_pass,
        "has_ssl": tech.has_ssl,
        "robots_txt_valid": tech.robots_txt_valid,
        "sitemap_exists": tech.sitemap_exists,
        "top_issues": tech.top_issues,
    }


def _serialize_content(content) -> dict | None:
    if not content:
        return None
    return {
        "pages_analyzed": content.pages_analyzed,
        "avg_quality_score": content.avg_quality_score,
        "thin_content_pages": content.thin_content_pages,
        "duplicate_groups": content.duplicate_groups,
        "missing_h1_pages": content.missing_h1_pages,
        "missing_meta_desc_pages": content.missing_meta_desc_pages,
        "low_word_count_pages": content.low_word_count_pages,
        "top_issues": content.top_issues,
    }


def _serialize_architecture(arch) -> dict | None:
    if not arch:
        return None
    return {
        "total_pages": arch.total_pages,
        "total_internal_links": arch.total_internal_links,
        "avg_depth": arch.avg_depth,
        "orphan_pages": arch.orphan_pages,
        "max_depth": arch.max_depth,
    }


def _serialize_aio(aio) -> dict | None:
    if not aio:
        return None
    return {
        "keywords_checked": aio.keywords_checked,
        "ai_overviews_present": aio.ai_overviews_present,
        "target_cited_count": aio.target_cited_count,
        "competitor_cited_count": aio.competitor_cited_count,
        "citation_rate": aio.citation_rate,
        "target_citation_rate": aio.target_citation_rate,
        "competitor_domains_cited": aio.competitor_domains_cited,
        "top_opportunities": aio.top_opportunities,
    }


def _serialize_geo(geo) -> dict | None:
    if not geo:
        return None
    return {
        "keywords_checked": geo.keywords_checked,
        "target_mentioned_count": geo.target_mentioned_count,
        "competitor_mentioned_count": geo.competitor_mentioned_count,
        "mention_rate": geo.mention_rate,
        "avg_mention_count": geo.avg_mention_count,
        "competitor_domains_mentioned": geo.competitor_domains_mentioned,
        "top_opportunities": geo.top_opportunities,
    }


@router.post("/analyze", response_model=SiteAnalyzeResponse)
async def analyze_site(
    body: SiteAnalyzeRequest,
    request: Request,
) -> SiteAnalyzeResponse:
    """Analyze a website: crawl, audit, discover rankings, generate recommendations.

    This is the main "analyze this website" endpoint. It runs:
    1. Full site crawl (technical SEO, content, architecture)
    2. Intelligent keyword extraction from content
    3. Ranking discovery for extracted keywords
    4. AI Overview (AIO) presence analysis
    5. Generative Engine (GEO) mention analysis
    6. Competitor ranking collection (if competitors provided)
    7. Unified search intelligence analysis
    8. Synthesized prioritized recommendations across SEO + AIO + GEO

    Note: This can take 60-180 seconds depending on site size and API limits.
    """
    service = _site_analysis_service(request)

    try:
        result = await service.analyze_site(
            domain=body.domain,
            max_pages=body.max_pages,
            max_keywords=body.max_keywords,
            country=body.country,
            device=body.device,
            competitors=body.competitors or None,
            deep_aio=body.deep_aio,
            deep_geo=body.deep_geo,
        )
    except Exception as e:
        logger = request.app.state.logger if hasattr(request.app.state, "logger") else None
        if logger:
            logger.exception("Site analysis failed for %s", body.domain)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Site analysis failed: {str(e)}",
        ) from e

    return SiteAnalyzeResponse(
        domain=result.domain,
        analyzed_at=result.analyzed_at.isoformat(),
        crawl_run_id=result.crawl_run_id,
        overall_score=round(result.overall_score, 1),
        technical_score=round(result.technical_score, 1),
        content_score=round(result.content_score, 1),
        ranking_score=round(result.ranking_score, 1),
        architecture_score=round(result.architecture_score, 1),
        aio_score=round(result.aio_score, 1),
        geo_score=round(result.geo_score, 1),
        rankings=_serialize_rankings(result.rankings),
        technical=_serialize_technical(result.technical),
        content=_serialize_content(result.content),
        architecture=_serialize_architecture(result.architecture),
        aio=_serialize_aio(result.aio),
        geo=_serialize_geo(result.geo),
        recommendations=[_serialize_recommendation(r) for r in result.recommendations],
    )


@router.post("/analyze/pdf")
async def analyze_site_pdf(
    body: SiteAnalyzeRequest,
    request: Request,
) -> StreamingResponse:
    """Analyze a website and return a comprehensive PDF report.

    Runs the full site analysis and generates a professional PDF report
    with scores, findings, and prioritized recommendations.
    """
    service = _site_analysis_service(request)
    renderer = PDFRenderer()

    try:
        result = await service.analyze_site(
            domain=body.domain,
            max_pages=body.max_pages,
            max_keywords=body.max_keywords,
            country=body.country,
            device=body.device,
            competitors=body.competitors or None,
            deep_aio=body.deep_aio,
            deep_geo=body.deep_geo,
        )
    except Exception as e:
        logger = request.app.state.logger if hasattr(request.app.state, "logger") else None
        if logger:
            logger.exception("Site analysis failed for %s", body.domain)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Site analysis failed: {str(e)}",
        ) from e

    try:
        pdf_bytes = renderer.render(result)
    except PDFGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    filename = f"site_analysis_{result.domain.replace('.', '_')}_{result.analyzed_at.strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/analyze/{domain}/status")
async def get_analysis_status(domain: str, request: Request):
    """Check if a site analysis is cached or running."""
    # Could implement caching here
    return {"status": "not_implemented", "domain": domain}


__all__ = ["router"]