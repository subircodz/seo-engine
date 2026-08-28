"""Site Analysis API endpoints — unified website intelligence."""

from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sie.api.auth import api_key_auth
from sie.domain.renderers.pdf_renderer import PDFGenerationError, PDFRenderer
from sie.domain.services.site_analysis import create_site_analysis_service

router = APIRouter(
    prefix="/api/site",
    tags=["site-analysis"],
    dependencies=[Depends(api_key_auth)],
)


class SiteAnalyzeRequest(BaseModel):
    """Request to analyze a website."""

    domain: str = Field(
        ..., description="Domain to analyze (e.g., example.com or https://example.com)"
    )
    max_pages: int = Field(default=100, ge=1, le=500, description="Maximum pages to crawl")
    max_keywords: int = Field(
        default=50, ge=1, le=200, description="Maximum keywords to check rankings for"
    )
    country: str = Field(default="us", description="Country code for search (e.g., us, gb, de)")
    target_countries: list[str] = Field(
        default=[],
        max_length=10,
        description='Additional countries to analyze (e.g., ["gb", "de", "in"])',
    )
    device: str = Field(default="desktop", description="Device type: desktop or mobile")
    competitors: list[str] = Field(
        default=[], max_length=5, description="Competitor domains to track"
    )
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
    country_rankings: list[dict] | None = None

    # V3 CategoryScore breakdowns
    content_breakdown: dict | None = None
    ranking_breakdown: dict | None = None
    architecture_breakdown: dict | None = None
    aio_breakdown: dict | None = None
    geo_breakdown: dict | None = None

    # Entity / Knowledge Graph analysis
    entity_analysis: dict | None = None

    # Page performance (deterministic HTML analysis)
    performance_summary: dict | None = None

    # Search opportunity analysis
    search_opportunities: dict | None = None

    # CrUX real-user Core Web Vitals
    crux_metrics: dict | None = None
    crux_status: str = "NOT_CONFIGURED"

    # Access / protection status
    access_status: dict | None = None
    website_type: dict | None = None
    report_metadata: dict | None = None

    # Prioritized recommendations
    recommendations: list[dict]


def _site_analysis_service(request: Request):
    """Get site analysis service from app state."""
    return create_site_analysis_service(
        crawl_service=request.app.state.crawl_service,
        audit_service=request.app.state.audit_service,
        content_service=request.app.state.content_service,
        search_provider=request.app.state.search_provider,
        repository=request.app.state.repository,
        crux_service=request.app.state.crux_service,
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
        "estimated_monthly_traffic_methodology": (
            "Heuristic estimate based on position-based CTR curve "
            "with nominal 1000 searches/month base volume. "
            "Not real traffic data — use Search Console for actual traffic."
        ),
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


def _serialize_country_ranking(cr) -> dict:
    return {
        "country_code": cr.country_code,
        "country_name": cr.country_name,
        "seo_score": round(cr.seo_score, 1),
        "aio_score": round(cr.aio_score, 1),
        "geo_score": round(cr.geo_score, 1),
        "overall_score": round(cr.overall_score, 1),
        "keywords_ranking": cr.keywords_ranking,
        "keywords_not_ranking": cr.keywords_not_ranking,
        "visibility_score": cr.visibility_score,
        "top_keywords": cr.top_keywords,
        "aio_citations": cr.aio_citations,
        "geo_mentions": cr.geo_mentions,
        "recommendations": [_serialize_recommendation(r) for r in cr.recommendations],
        "action_items": cr.action_items,
    }


def _serialize_metric(m) -> dict:
    """Serialize a single AnalysisMetric to dict."""
    return {
        "metric_name": m.metric_name,
        "category": m.category,
        "metric_type": m.metric_type,
        "expected": m.expected,
        "normalized_score": m.normalized_score,
        "weight": m.weight,
        "raw_value": m.raw_value,
        "raw_unit": m.raw_unit,
        "raw_evidence": m.raw_evidence,
        "normalization_method": m.normalization_method,
        "score_contribution": m.score_contribution,
        "status": m.status,
        "evidence": m.evidence,
        "evidence_quality": m.evidence_quality,
        "affected_urls": m.affected_urls,
        "affected_keywords": m.affected_keywords,
        "why_it_matters": m.why_it_matters,
        "remediation": m.remediation,
        "implementation": m.implementation,
        "reference_url": m.reference_url,
        "limitations": m.limitations,
        "sample_size": m.sample_size,
        "data_coverage": m.data_coverage,
        "coverage_methodology": m.coverage_methodology,
        "confidence": m.confidence,
    }


def _serialize_breakdown(breakdown) -> dict | None:
    """Serialize a CategoryScore to dict for the API response."""
    if not breakdown:
        return None
    return {
        "category_name": breakdown.category_name,
        "overall_score": breakdown.overall_score,
        "score_status": breakdown.score_status,
        "scoring_methodology": breakdown.scoring_methodology,
        "metrics": [_serialize_metric(m) for m in breakdown.metrics],
        "sample_size": breakdown.sample_size,
        "data_coverage": breakdown.data_coverage,
        "confidence": breakdown.confidence,
        "confidence_factors": breakdown.confidence_factors,
        "limitations": breakdown.limitations,
        "evidence_quality_summary": breakdown.evidence_quality_summary,
        "data_source": breakdown.data_source,
        "observation_date": breakdown.observation_date,
    }


def _serialize_entity_analysis(entity) -> dict | None:
    """Serialize entity/knowledge graph analysis."""
    if not entity:
        return None
    return {
        "entities_extracted": entity.entities_extracted,
        "unique_entities": entity.unique_entities,
        "entity_types": entity.entity_types,
        "wikipedia_aligned": entity.wikipedia_aligned,
        "wikidata_aligned": entity.wikidata_aligned,
        "knowledge_graph_coverage": entity.knowledge_graph_coverage,
        "entity_salience_scores": entity.entity_salience_scores,
        "missing_entity_types": entity.missing_entity_types,
        "schema_entity_alignment": entity.schema_entity_alignment,
        "recommendations": entity.recommendations,
        "score": entity.score,
    }


def _serialize_performance_summary(perf) -> dict | None:
    """Serialize deterministic page performance summary."""
    if not perf:
        return None
    return {
        "pages_analyzed": perf.pages_analyzed,
        "avg_performance_score": perf.avg_performance_score,
        "pages_above_threshold": perf.pages_above_threshold,
        "pages_below_threshold": perf.pages_below_threshold,
        "total_findings": perf.total_findings,
        "avg_html_size": perf.avg_html_size,
        "avg_content_efficiency": perf.avg_content_efficiency,
        "top_issues": perf.top_issues,
        "largest_pages": perf.largest_pages,
        "least_efficient": perf.least_efficient,
        "findings_by_severity": perf.findings_by_severity,
        "score": perf.score,
        "methodology": perf.methodology,
        "limitations": perf.limitations,
    }


def _serialize_search_opportunities(opps) -> dict | None:
    """Serialize search opportunity analysis."""
    if not opps:
        return None
    result: dict[str, Any] = {
        "total_opportunities": opps.total_opportunities,
        "competitor_gaps": [],
        "weak_rankings": [],
        "content_gaps": [],
    }
    for gap in opps.competitor_gaps:
        result["competitor_gaps"].append(
            {
                "keyword": gap.keyword,
                "competitor_domain": gap.competitor_domain,
                "competitor_position": gap.competitor_position,
                "severity": gap.severity,
                "confidence_score": gap.confidence_score,
                "estimated_improvement": gap.estimated_improvement,
            }
        )
    for wr in opps.weak_ranking_opportunities:
        result["weak_rankings"].append(
            {
                "keyword": wr.keyword,
                "target_position": wr.target_position,
                "severity": wr.severity,
                "confidence_score": wr.confidence_score,
                "estimated_improvement": wr.estimated_improvement,
            }
        )
    for cg in opps.content_gaps:
        result["content_gaps"].append(
            {
                "keyword": cg.keyword,
                "competitor_domains": list(cg.competitor_domains),
                "average_competitor_position": cg.average_competitor_position,
                "primary_competitor": cg.primary_competitor,
                "confidence_score": cg.confidence_score,
                "content_description_hint": cg.content_description_hint,
            }
        )
    return result


def _serialize_crux_metrics(crux) -> dict | None:
    """Serialize CrUX real-user Core Web Vitals."""
    if not crux:
        return None
    return {
        "origin": crux.origin,
        "lcp_p75": crux.lcp_p75,
        "fid_p75": crux.fid_p75,
        "cls_p75": crux.cls_p75,
        "inp_p75": crux.inp_p75,
        "ttfb_p75": crux.ttfb_p75,
        "lcp_good": crux.lcp_good,
        "fid_good": crux.fid_good,
        "cls_good": crux.cls_good,
        "inp_good": crux.inp_good,
        "lcp_poor": crux.lcp_poor,
        "fid_poor": crux.fid_poor,
        "cls_poor": crux.cls_poor,
        "form_factor": crux.form_factor,
        "effective_date": crux.effective_date,
    }


def _serialize_access_status(status) -> dict | None:
    """Serialize access/protection status."""
    if not status:
        return None
    return {
        "accessible": status.accessible,
        "protection_detected": status.protection_detected,
        "protection_details": status.protection_details,
        "status_code": status.status_code,
        "analysis_status": status.analysis_status,
        "block_reason": status.block_reason,
        "analyzed_page_is_challenge": status.analyzed_page_is_challenge,
    }


def _serialize_website_type(wt) -> dict | None:
    """Serialize website technology info."""
    if not wt:
        return None
    return {
        "technology": wt.technology,
        "confidence": wt.confidence,
        "evidence": wt.evidence[:5],
        "cms": wt.cms,
        "framework": wt.framework,
        "language": wt.language,
        "server": wt.server,
        "cdn": wt.cdn,
    }


def _serialize_report_metadata(meta) -> dict | None:
    """Serialize report execution metadata."""
    if not meta:
        return None
    return {
        "target_url": meta.target_url,
        "analysis_date": meta.analysis_date,
        "analysis_started": meta.analysis_started,
        "analysis_completed": meta.analysis_completed,
        "country": meta.country,
        "device": meta.device,
        "search_engine": meta.search_engine,
        "crawler_mode": meta.crawler_mode,
        "analysis_duration_seconds": meta.analysis_duration_seconds,
        "pages_crawled": meta.pages_crawled,
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
            target_countries=body.target_countries or None,
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
            detail=f"Site analysis failed: {e!s}",
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
        country_rankings=(
            [_serialize_country_ranking(cr) for cr in result.country_rankings]
            if result.country_rankings
            else None
        ),
        content_breakdown=_serialize_breakdown(result.content_breakdown),
        ranking_breakdown=_serialize_breakdown(result.ranking_breakdown),
        architecture_breakdown=_serialize_breakdown(result.architecture_breakdown),
        aio_breakdown=_serialize_breakdown(result.aio_breakdown),
        geo_breakdown=_serialize_breakdown(result.geo_breakdown),
        entity_analysis=_serialize_entity_analysis(result.entity_analysis),
        performance_summary=_serialize_performance_summary(result.performance_summary),
        search_opportunities=_serialize_search_opportunities(result.search_opportunities),
        crux_metrics=_serialize_crux_metrics(result.crux_metrics),
        crux_status=result.crux_status,
        access_status=_serialize_access_status(result.access_status),
        website_type=_serialize_website_type(result.website_type),
        report_metadata=_serialize_report_metadata(result.report_metadata),
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
            target_countries=body.target_countries or None,
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
            detail=f"Site analysis failed: {e!s}",
        ) from e

    try:
        pdf_bytes = renderer.render(result)
    except PDFGenerationError as exc:
        logger = request.app.state.logger if hasattr(request.app.state, "logger") else None
        if logger:
            logger.exception("PDF generation failed for %s", body.domain)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {exc!s}",
        ) from exc
    except Exception as exc:
        logger = request.app.state.logger if hasattr(request.app.state, "logger") else None
        if logger:
            logger.exception("PDF rendering failed for %s", body.domain)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF rendering failed: {type(exc).__name__}: {exc!s}",
        ) from exc

    date_str = result.analyzed_at.strftime('%Y%m%d')
    domain_str = result.domain.replace('.', '_')
    filename = f"site_analysis_{domain_str}_{date_str}.pdf"
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
