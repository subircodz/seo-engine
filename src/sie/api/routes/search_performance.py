"""Search Performance, Entity, Optimization, and Reporting API endpoints (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sie.api.auth import api_key_auth
from sie.domain.engines.search_entity import (
    analyze_entity_visibility,
    detect_entity_gaps,
    extract_entities_from_content,
)
from sie.domain.engines.search_optimization import synthesize_optimization_recommendations
from sie.domain.engines.search_performance import (
    analyze_dataset_performance,
)
from sie.domain.engines.search_report import generate_intelligence_report
from sie.domain.models.search_entity import EntitySignal

router = APIRouter(
    prefix="/api/search-intelligence",
    tags=["search-performance"],
    dependencies=[Depends(api_key_auth)],
)


# ── Request / Response models ────────────────────────────────────────────


class PagePerformanceRequest(BaseModel):
    url: str
    html_size: int = 0
    visible_text: str = ""
    heading_count: int = 0
    link_count: int = 0
    image_count: int = 0
    images_without_alt: int = 0
    css_count: int = 0
    css_total_bytes: int = 0
    js_count: int = 0
    js_total_bytes: int = 0
    image_total_bytes: int = 0
    inline_css_bytes: int = 0
    inline_js_bytes: int = 0


class PerformanceAnalysisRequest(BaseModel):
    dataset_id: str = "default"
    pages: list[PagePerformanceRequest] = []


class PerformanceAnalysisResponse(BaseModel):
    dataset_id: str
    total_pages: int
    avg_html_size: float
    avg_content_efficiency: float
    avg_performance_score: float
    pages_above_threshold: int
    pages_below_threshold: int
    total_findings: int
    findings_by_severity: dict[str, int]


class EntityExtractionRequest(BaseModel):
    text: str
    min_frequency: int = 1
    max_entities: int = 200


class EntityObservationRequest(BaseModel):
    keyword: str
    content_text: str = ""
    target_entities: list[dict] = []
    competitor_entities: list[dict] = []


class EntityAnalysisRequest(BaseModel):
    dataset_id: str = "default"
    observations: list[EntityObservationRequest] = []
    target_domain: str = ""


class EntityGapRequest(BaseModel):
    target_entities: list[dict] = []
    competitor_entities: list[dict] = []
    min_competitor_frequency: int = 2


class EntityAnalysisResponse(BaseModel):
    dataset_id: str
    total_unique_entities: int
    overall_coverage: float
    keyword_count: int


class EntityGapResponse(BaseModel):
    total_gaps: int
    gaps: list[dict]


class OptimizationAnalysisRequest(BaseModel):
    dataset_id: str = "default"
    visibility_score: float = 0.0
    keywords_not_ranking: int = 0
    total_keywords: int = 0
    top_10_count: int = 0
    featured_snippet_occurrences: int = 0
    featured_snippet_owned: int = 0
    people_also_ask_occurrences: int = 0
    people_also_ask_owned: int = 0
    cannibalization_count: int = 0
    extreme_cannibalization_count: int = 0
    volatile_keyword_count: int = 0
    total_volatility_keywords: int = 0
    competitor_gap_count: int = 0
    weak_ranking_count: int = 0
    content_gap_count: int = 0
    total_opportunities: int = 0
    aio_total_keywords: int = 0
    aio_keywords_with_overview: int = 0
    aio_target_cited_count: int = 0
    geo_total_keywords: int = 0
    geo_keywords_mentioned: int = 0
    geo_overall_mention_rate: float = 0.0
    avg_performance_score: float = 0.0
    pages_below_threshold: int = 0
    performance_total_pages: int = 0
    entity_coverage: float = 0.0
    entity_gap_count: int = 0


class OptimizationAnalysisResponse(BaseModel):
    dataset_id: str
    total_recommendations: int
    high_priority_count: int
    estimated_quick_wins: int
    recommendations_by_category: dict[str, int]
    summary: str


class ReportRequest(BaseModel):
    dataset_id: str = "default"
    visibility_score: float = 0.0
    total_keywords: int = 0
    keywords_ranking: int = 0
    keywords_not_ranking: int = 0
    top_10_count: int = 0
    serp_feature_count: int = 0
    cannibalization_count: int = 0
    extreme_cannibalization_count: int = 0
    volatile_keyword_count: int = 0
    total_opportunities: int = 0
    competitor_gap_count: int = 0
    weak_ranking_count: int = 0
    content_gap_count: int = 0
    aio_total_keywords: int = 0
    aio_keywords_with_overview: int = 0
    aio_target_cited_count: int = 0
    geo_total_keywords: int = 0
    geo_keywords_mentioned: int = 0
    performance_total_pages: int = 0
    avg_performance_score: float = 0.0
    performance_findings_count: int = 0
    entity_total_unique: int = 0
    entity_coverage: float = 0.0
    entity_gap_count: int = 0
    optimization_recommendation_count: int = 0
    high_priority_optimization_count: int = 0
    quick_wins_count: int = 0


class ReportResponse(BaseModel):
    dataset_id: str
    summary: str
    total_findings: int
    total_recommendations: int
    component_count: int
    action_item_count: int


# ── Performance endpoints ────────────────────────────────────────────────


@router.post("/performance/analyze", response_model=PerformanceAnalysisResponse)
async def analyze_performance(request: PerformanceAnalysisRequest):
    """Analyze page and dataset performance characteristics."""
    pages = [p.model_dump() for p in request.pages]
    result = analyze_dataset_performance(request.dataset_id, tuple(pages))
    return PerformanceAnalysisResponse(
        dataset_id=result.dataset_id,
        total_pages=result.total_pages,
        avg_html_size=result.avg_html_size,
        avg_content_efficiency=result.avg_content_efficiency,
        avg_performance_score=result.avg_performance_score,
        pages_above_threshold=result.pages_above_threshold,
        pages_below_threshold=result.pages_below_threshold,
        total_findings=result.total_findings,
        findings_by_severity=result.findings_by_severity,
    )


# ── Entity endpoints ────────────────────────────────────────────────────


@router.post("/entity/extract", response_model=dict)
async def extract_entities(request: EntityExtractionRequest):
    """Extract entities from content text."""
    entities = extract_entities_from_content(
        request.text,
        min_frequency=request.min_frequency,
        max_entities=request.max_entities,
    )
    return {
        "total_entities": len(entities),
        "entities": [
            {
                "text": e.text,
                "category": e.category.value,
                "frequency": e.frequency,
                "confidence": e.confidence,
            }
            for e in entities
        ],
    }


@router.post("/entity/analyze", response_model=EntityAnalysisResponse)
async def analyze_entity(request: EntityAnalysisRequest):
    """Analyze entity visibility across observations."""
    obs = []
    for o in request.observations:
        obs.append(
            {
                "keyword": o.keyword,
                "content_text": o.content_text,
                "target_entities": tuple(
                    EntitySignal(
                        text=e.get("text", ""),
                        frequency=e.get("frequency", 1),
                        is_target=e.get("is_target", False),
                    )
                    for e in o.target_entities
                ),
                "competitor_entities": tuple(
                    EntitySignal(
                        text=e.get("text", ""),
                        frequency=e.get("frequency", 1),
                    )
                    for e in o.competitor_entities
                ),
            }
        )
    result = analyze_entity_visibility(tuple(obs), request.target_domain)
    return EntityAnalysisResponse(
        dataset_id=result.dataset_id,
        total_unique_entities=result.total_unique_entities,
        overall_coverage=result.overall_coverage,
        keyword_count=len(result.keyword_results),
    )


@router.post("/entity/gaps", response_model=EntityGapResponse)
async def detect_entity_gaps_endpoint(request: EntityGapRequest):
    """Detect entity gaps between target and competitors."""
    target = tuple(
        EntitySignal(
            text=e.get("text", ""),
            frequency=e.get("frequency", 1),
            is_target=e.get("is_target", False),
        )
        for e in request.target_entities
    )
    competitor = tuple(
        EntitySignal(
            text=e.get("text", ""),
            frequency=e.get("frequency", 1),
        )
        for e in request.competitor_entities
    )
    gaps = detect_entity_gaps(
        target,
        competitor,
        min_competitor_frequency=request.min_competitor_frequency,
    )
    return EntityGapResponse(
        total_gaps=len(gaps),
        gaps=[
            {
                "entity_text": g.entity_text,
                "entity_category": g.entity_category.value,
                "competitor_frequency": g.competitor_frequency,
                "recommended_action": g.recommended_action,
            }
            for g in gaps
        ],
    )


# ── Optimization endpoint ────────────────────────────────────────────────


@router.post("/optimization/analyze", response_model=OptimizationAnalysisResponse)
async def analyze_optimization(request: OptimizationAnalysisRequest):
    """Synthesise cross-engine optimization recommendations."""
    result = synthesize_optimization_recommendations(
        request.dataset_id,
        visibility_score=request.visibility_score,
        keywords_not_ranking=request.keywords_not_ranking,
        total_keywords=request.total_keywords,
        top_10_count=request.top_10_count,
        featured_snippet_occurrences=request.featured_snippet_occurrences,
        featured_snippet_owned=request.featured_snippet_owned,
        people_also_ask_occurrences=request.people_also_ask_occurrences,
        people_also_ask_owned=request.people_also_ask_owned,
        cannibalization_count=request.cannibalization_count,
        extreme_cannibalization_count=request.extreme_cannibalization_count,
        volatile_keyword_count=request.volatile_keyword_count,
        total_volatility_keywords=request.total_volatility_keywords,
        competitor_gap_count=request.competitor_gap_count,
        weak_ranking_count=request.weak_ranking_count,
        content_gap_count=request.content_gap_count,
        total_opportunities=request.total_opportunities,
        aio_total_keywords=request.aio_total_keywords,
        aio_keywords_with_overview=request.aio_keywords_with_overview,
        aio_target_cited_count=request.aio_target_cited_count,
        geo_total_keywords=request.geo_total_keywords,
        geo_keywords_mentioned=request.geo_keywords_mentioned,
        geo_overall_mention_rate=request.geo_overall_mention_rate,
        avg_performance_score=request.avg_performance_score,
        pages_below_threshold=request.pages_below_threshold,
        performance_total_pages=request.performance_total_pages,
        entity_coverage=request.entity_coverage,
        entity_gap_count=request.entity_gap_count,
    )
    return OptimizationAnalysisResponse(
        dataset_id=result.dataset_id,
        total_recommendations=result.total_recommendations,
        high_priority_count=result.high_priority_count,
        estimated_quick_wins=result.estimated_quick_wins,
        recommendations_by_category=result.recommendations_by_category,
        summary=result.summary,
    )


# ── Report endpoint ──────────────────────────────────────────────────────


@router.post("/report", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """Generate a consolidated intelligence report."""
    result = generate_intelligence_report(
        request.dataset_id,
        visibility_score=request.visibility_score,
        total_keywords=request.total_keywords,
        keywords_ranking=request.keywords_ranking,
        keywords_not_ranking=request.keywords_not_ranking,
        top_10_count=request.top_10_count,
        serp_feature_count=request.serp_feature_count,
        cannibalization_count=request.cannibalization_count,
        extreme_cannibalization_count=request.extreme_cannibalization_count,
        volatile_keyword_count=request.volatile_keyword_count,
        total_opportunities=request.total_opportunities,
        competitor_gap_count=request.competitor_gap_count,
        weak_ranking_count=request.weak_ranking_count,
        content_gap_count=request.content_gap_count,
        aio_total_keywords=request.aio_total_keywords,
        aio_keywords_with_overview=request.aio_keywords_with_overview,
        aio_target_cited_count=request.aio_target_cited_count,
        geo_total_keywords=request.geo_total_keywords,
        geo_keywords_mentioned=request.geo_keywords_mentioned,
        performance_total_pages=request.performance_total_pages,
        avg_performance_score=request.avg_performance_score,
        performance_findings_count=request.performance_findings_count,
        entity_total_unique=request.entity_total_unique,
        entity_coverage=request.entity_coverage,
        entity_gap_count=request.entity_gap_count,
        optimization_recommendation_count=request.optimization_recommendation_count,
        high_priority_optimization_count=request.high_priority_optimization_count,
        quick_wins_count=request.quick_wins_count,
    )
    return ReportResponse(
        dataset_id=result.dataset_id,
        summary=result.summary,
        total_findings=result.total_findings,
        total_recommendations=result.total_recommendations,
        component_count=len(result.components),
        action_item_count=len(result.action_items),
    )
