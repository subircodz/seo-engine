"""Search Intelligence API endpoints — AIO, GEO, unified intelligence, and analysis."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from sie.domain.engines.search_aio import analyze_aio_observations
from sie.domain.engines.search_geo import analyze_geo_observations
from sie.domain.models.search import CompetitorRanking, RankingObservation, SearchDataset
from sie.domain.models.search_aio import AIOverviewObservation, AIOverviewResult
from sie.domain.models.search_geo import GEOObservation, GEOResult
from sie.domain.services.search_intelligence import (
    SearchIntelligenceResult,
    SearchIntelligenceService,
)
from sie.domain.services.search_opportunity import SearchOpportunityResult

router = APIRouter(prefix="/api/search-intelligence", tags=["search-intelligence"])


# ── Request / Response models ────────────────────────────────────────────


class AIOverviewObservationRequest(BaseModel):
    keyword: str
    ai_type: str = "ai_overview"
    present: bool = True
    target_cited: bool = False
    target_domain: str = ""
    citation_count: int = 0
    competitor_cited_domains: list[str] = []


class AIOAnalysisRequest(BaseModel):
    dataset_id: str
    observations: list[AIOverviewObservationRequest]
    total_keywords: int = 0


class AIOCitationResponse(BaseModel):
    domain: str
    url: str
    position: int
    source_type: str
    title: str


class AIOverviewMetricsResponse(BaseModel):
    keyword: str
    observation_count: int
    ai_overview_present_count: int
    target_cited_count: int
    competitor_cited_count: int
    citation_rate: float
    target_citation_rate: float


class AIOverviewDatasetMetricsResponse(BaseModel):
    dataset_id: str
    total_keywords: int
    keywords_with_ai_overview: int
    keywords_target_cited: int
    total_ai_overview_observations: int
    total_citations: int
    target_citation_rate: float
    competitor_cited_domains: list[str]


class AIOAnalysisResponse(BaseModel):
    dataset_id: str
    keyword_metrics: list[AIOverviewMetricsResponse]
    dataset_metrics: AIOverviewDatasetMetricsResponse


class GEOObservationRequest(BaseModel):
    keyword: str
    engine_type: str = "other"
    target_mentioned: bool = False
    target_domain: str = ""
    mention_count: int = 0
    competitor_domains: list[str] = []
    citation_urls: list[str] = []
    answer_length: int = 0


class GEOAnalysisRequest(BaseModel):
    dataset_id: str
    observations: list[GEOObservationRequest]
    total_keywords: int = 0


class GEOMetricsResponse(BaseModel):
    keyword: str
    observation_count: int
    target_mentioned_count: int
    competitor_mentioned_count: int
    mention_rate: float
    avg_mention_count: float


class GEODatasetMetricsResponse(BaseModel):
    dataset_id: str
    total_keywords: int
    keywords_target_mentioned: int
    total_observations: int
    total_target_mentions: int
    overall_mention_rate: float
    competitor_domain_counts: dict[str, int]


class GEOAnalysisResponse(BaseModel):
    dataset_id: str
    keyword_metrics: list[GEOMetricsResponse]
    dataset_metrics: GEODatasetMetricsResponse


class CannibalizationFindingResponse(BaseModel):
    keyword: str
    competing_urls: tuple[str, ...]
    severity: str
    positions: tuple[int, ...]


class CannibalizationAnalysisResponse(BaseModel):
    findings: list[CannibalizationFindingResponse]
    total_findings: int
    keywords_affected: int


class VolatilityMetricsResponse(BaseModel):
    keyword: str
    volatility: float
    severity: str


class VolatilityAnalysisResponse(BaseModel):
    metrics: list[VolatilityMetricsResponse]
    total_keywords: int
    volatile_count: int


class OpportunityResponse(BaseModel):
    keyword: str
    target_url: str
    target_domain: str
    competitor_domain: str
    target_position: int | None
    competitor_position: int | None
    opportunity_type: str
    severity: str
    confidence_score: float
    estimated_improvement: str | None


class ContentGapResponse(BaseModel):
    keyword: str
    target_domain: str
    competitor_domains: tuple[str, ...]
    competitor_urls: tuple[str, ...]
    competitor_positions: tuple[int, ...]
    average_competitor_position: float
    primary_competitor: str
    confidence_score: float
    content_description_hint: str | None


class OpportunityAnalysisResponse(BaseModel):
    competitor_gaps: list[OpportunityResponse]
    weak_ranking_opportunities: list[OpportunityResponse]
    content_gaps: list[ContentGapResponse]
    total_opportunities: int


class SearchIntelligenceSummaryResponse(BaseModel):
    total_keywords: int
    keywords_ranking: int
    keywords_not_ranking: int
    visibility_score: float
    cannibalization_count: int
    volatile_keyword_count: int
    opportunity_count: int
    serp_feature_opportunity_count: int
    competitor_gap_count: int
    weak_ranking_count: int
    content_gap_count: int


class SearchRecommendationResponse(BaseModel):
    category: str
    priority: str
    title: str
    description: str
    affected_keywords: list[str]
    affected_urls: list[str]
    confidence: float


class SearchIntelligenceAnalysisResponse(BaseModel):
    dataset_id: str
    summary: SearchIntelligenceSummaryResponse
    recommendations: list[SearchRecommendationResponse]
    cannibalization_count: int
    volatility_count: int
    opportunity_count: int


class AnalyzeDatasetRequest(BaseModel):
    dataset_id: str
    observations: list[dict] = []
    competitor_rankings: list[dict] = []
    total_keywords: int = 0


# ── AIO Analysis ─────────────────────────────────────────────────────────


def _parse_ai_overview_observation(
    req: AIOverviewObservationRequest,
) -> AIOverviewObservation:
    from sie.domain.models.search_aio import AIOverviewType

    try:
        ai_type = AIOverviewType(req.ai_type)
    except ValueError:
        ai_type = AIOverviewType.OTHER

    return AIOverviewObservation(
        keyword=req.keyword,
        ai_type=ai_type,
        present=req.present,
        target_cited=req.target_cited,
        target_domain=req.target_domain,
        citation_count=req.citation_count,
        competitor_cited_domains=tuple(req.competitor_cited_domains),
    )


@router.post("/aio/analyze", response_model=AIOAnalysisResponse)
async def analyze_aio(body: AIOAnalysisRequest) -> AIOAnalysisResponse:
    """Analyze AI Overview observations for a dataset."""
    observations = tuple(_parse_ai_overview_observation(obs) for obs in body.observations)
    result = analyze_aio_observations(body.dataset_id, observations, body.total_keywords)
    return _aio_result_to_response(result)


def _aio_result_to_response(result: AIOverviewResult) -> AIOAnalysisResponse:
    return AIOAnalysisResponse(
        dataset_id=result.dataset_id,
        keyword_metrics=[
            AIOverviewMetricsResponse(
                keyword=km.keyword,
                observation_count=km.observation_count,
                ai_overview_present_count=km.ai_overview_present_count,
                target_cited_count=km.target_cited_count,
                competitor_cited_count=km.competitor_cited_count,
                citation_rate=km.citation_rate,
                target_citation_rate=km.target_citation_rate,
            )
            for km in result.keyword_metrics
        ],
        dataset_metrics=AIOverviewDatasetMetricsResponse(
            dataset_id=result.dataset_metrics.dataset_id,
            total_keywords=result.dataset_metrics.total_keywords,
            keywords_with_ai_overview=result.dataset_metrics.keywords_with_ai_overview,
            keywords_target_cited=result.dataset_metrics.keywords_target_cited,
            total_ai_overview_observations=result.dataset_metrics.total_ai_overview_observations,
            total_citations=result.dataset_metrics.total_citations,
            target_citation_rate=result.dataset_metrics.target_citation_rate,
            competitor_cited_domains=list(result.dataset_metrics.competitor_cited_domains),
        ),
    )


# ── GEO Analysis ─────────────────────────────────────────────────────────


def _parse_geo_observation(req: GEOObservationRequest) -> GEOObservation:
    from sie.domain.models.search_geo import GenerativeEngineType

    try:
        engine_type = GenerativeEngineType(req.engine_type)
    except ValueError:
        engine_type = GenerativeEngineType.OTHER

    return GEOObservation(
        keyword=req.keyword,
        engine_type=engine_type,
        target_mentioned=req.target_mentioned,
        target_domain=req.target_domain,
        mention_count=req.mention_count,
        competitor_domains=tuple(req.competitor_domains),
        citation_urls=tuple(req.citation_urls),
        answer_length=req.answer_length,
    )


@router.post("/geo/analyze", response_model=GEOAnalysisResponse)
async def analyze_geo(body: GEOAnalysisRequest) -> GEOAnalysisResponse:
    """Analyze Generative Engine Optimization observations for a dataset."""
    observations = tuple(_parse_geo_observation(obs) for obs in body.observations)
    result = analyze_geo_observations(body.dataset_id, observations, body.total_keywords)
    return _geo_result_to_response(result)


def _geo_result_to_response(result: GEOResult) -> GEOAnalysisResponse:
    return GEOAnalysisResponse(
        dataset_id=result.dataset_id,
        keyword_metrics=[
            GEOMetricsResponse(
                keyword=km.keyword,
                observation_count=km.observation_count,
                target_mentioned_count=km.target_mentioned_count,
                competitor_mentioned_count=km.competitor_mentioned_count,
                mention_rate=km.mention_rate,
                avg_mention_count=km.avg_mention_count,
            )
            for km in result.keyword_metrics
        ],
        dataset_metrics=GEODatasetMetricsResponse(
            dataset_id=result.dataset_metrics.dataset_id,
            total_keywords=result.dataset_metrics.total_keywords,
            keywords_target_mentioned=result.dataset_metrics.keywords_target_mentioned,
            total_observations=result.dataset_metrics.total_observations,
            total_target_mentions=result.dataset_metrics.total_target_mentions,
            overall_mention_rate=result.dataset_metrics.overall_mention_rate,
            competitor_domain_counts=result.dataset_metrics.competitor_domain_counts,
        ),
    )


# ── Cannibalization Analysis ─────────────────────────────────────────────


@router.post("/cannibalization/analyze", response_model=CannibalizationAnalysisResponse)
async def analyze_cannibalization(body: AnalyzeDatasetRequest) -> CannibalizationAnalysisResponse:
    """Analyze cannibalization for a dataset."""
    from sie.domain.services.cannibalization import CannibalizationDetector

    observations = _parse_ranking_observations(body.observations)
    detector = CannibalizationDetector()
    findings = detector.detect_cannibalization(observations)

    keywords_affected = len({f.keyword for f in findings})

    return CannibalizationAnalysisResponse(
        findings=[
            CannibalizationFindingResponse(
                keyword=f.keyword,
                competing_urls=f.competing_urls,
                severity=f.severity,
                positions=f.positions,
            )
            for f in findings
        ],
        total_findings=len(findings),
        keywords_affected=keywords_affected,
    )


# ── Volatility Analysis ──────────────────────────────────────────────────


@router.post("/volatility/analyze", response_model=VolatilityAnalysisResponse)
async def analyze_volatility(body: AnalyzeDatasetRequest) -> VolatilityAnalysisResponse:
    """Analyze ranking volatility for a dataset."""
    from sie.domain.services.ranking_volatility import RankingVolatilityService

    observations = _parse_ranking_observations(body.observations)
    service = RankingVolatilityService()
    metrics = service.calculate_volatility_by_keyword(observations)

    volatile_count = sum(1 for m in metrics if m.volatility >= 0.3)

    return VolatilityAnalysisResponse(
        metrics=[
            VolatilityMetricsResponse(
                keyword=m.keyword,
                volatility=m.volatility,
                severity=m.severity,
            )
            for m in metrics
        ],
        total_keywords=len(metrics),
        volatile_count=volatile_count,
    )


# ── Opportunity Analysis ─────────────────────────────────────────────────


@router.post("/opportunities/analyze", response_model=OpportunityAnalysisResponse)
async def analyze_opportunities(body: AnalyzeDatasetRequest) -> OpportunityAnalysisResponse:
    """Analyze search opportunities for a dataset."""
    from sie.domain.engines.search_analytics import analyze_search_dataset
    from sie.domain.services.search_opportunity import SearchOpportunityService

    observations = _parse_ranking_observations(body.observations)
    competitor_rankings = _parse_competitor_rankings(body.competitor_rankings)

    dataset = SearchDataset(
        dataset_id=body.dataset_id,
        name="api-analysis",
        source="api",
        total_keywords=body.total_keywords,
        total_observations=len(observations),
    )

    analytics = analyze_search_dataset(dataset, observations, competitor_rankings)
    service = SearchOpportunityService()
    result = service.calculate_opportunities(dataset, analytics, competitor_rankings)

    return _opportunity_result_to_response(result)


def _opportunity_result_to_response(result: SearchOpportunityResult) -> OpportunityAnalysisResponse:
    return OpportunityAnalysisResponse(
        competitor_gaps=[
            OpportunityResponse(
                keyword=g.keyword,
                target_url=g.target_url,
                target_domain=g.target_domain,
                competitor_domain=g.competitor_domain,
                target_position=g.target_position,
                competitor_position=g.competitor_position,
                opportunity_type=g.opportunity_type,
                severity=g.severity,
                confidence_score=g.confidence_score,
                estimated_improvement=g.estimated_improvement,
            )
            for g in result.competitor_gaps
        ],
        weak_ranking_opportunities=[
            OpportunityResponse(
                keyword=w.keyword,
                target_url=w.target_url,
                target_domain=w.target_domain,
                competitor_domain=w.competitor_domain,
                target_position=w.target_position,
                competitor_position=w.competitor_position,
                opportunity_type=w.opportunity_type,
                severity=w.severity,
                confidence_score=w.confidence_score,
                estimated_improvement=w.estimated_improvement,
            )
            for w in result.weak_ranking_opportunities
        ],
        content_gaps=[
            ContentGapResponse(
                keyword=g.keyword,
                target_domain=g.target_domain,
                competitor_domains=g.competitor_domains,
                competitor_urls=g.competitor_urls,
                competitor_positions=g.competitor_positions,
                average_competitor_position=g.average_competitor_position,
                primary_competitor=g.primary_competitor,
                confidence_score=g.confidence_score,
                content_description_hint=g.content_description_hint,
            )
            for g in result.content_gaps
        ],
        total_opportunities=result.total_opportunities,
    )


# ── Unified Search Intelligence ──────────────────────────────────────────


@router.post("/analyze", response_model=SearchIntelligenceAnalysisResponse)
async def analyze_search_intelligence(
    body: AnalyzeDatasetRequest,
) -> SearchIntelligenceAnalysisResponse:
    """Run full search intelligence analysis combining all capabilities."""
    observations = _parse_ranking_observations(body.observations)
    competitor_rankings = _parse_competitor_rankings(body.competitor_rankings)

    dataset = SearchDataset(
        dataset_id=body.dataset_id,
        name="api-analysis",
        source="api",
        total_keywords=body.total_keywords,
        total_observations=len(observations),
    )

    service = SearchIntelligenceService()
    result = service.analyze(dataset, observations, competitor_rankings)

    return _intelligence_result_to_response(result)


def _intelligence_result_to_response(
    result: SearchIntelligenceResult,
) -> SearchIntelligenceAnalysisResponse:
    return SearchIntelligenceAnalysisResponse(
        dataset_id=result.dataset_id,
        summary=SearchIntelligenceSummaryResponse(
            total_keywords=result.summary.total_keywords,
            keywords_ranking=result.summary.keywords_ranking,
            keywords_not_ranking=result.summary.keywords_not_ranking,
            visibility_score=result.summary.visibility_score,
            cannibalization_count=result.summary.cannibalization_count,
            volatile_keyword_count=result.summary.volatile_keyword_count,
            opportunity_count=result.summary.opportunity_count,
            serp_feature_opportunity_count=result.summary.serp_feature_opportunity_count,
            competitor_gap_count=result.summary.competitor_gap_count,
            weak_ranking_count=result.summary.weak_ranking_count,
            content_gap_count=result.summary.content_gap_count,
        ),
        recommendations=[
            SearchRecommendationResponse(
                category=r.category.value,
                priority=r.priority.value,
                title=r.title,
                description=r.description,
                affected_keywords=list(r.affected_keywords),
                affected_urls=list(r.affected_urls),
                confidence=r.confidence,
            )
            for r in result.recommendations
        ],
        cannibalization_count=len(result.cannibalization_findings),
        volatility_count=len(result.volatility_metrics),
        opportunity_count=(
            result.opportunity_result.total_opportunities if result.opportunity_result else 0
        ),
    )


# ── Helpers ──────────────────────────────────────────────────────────────


def _parse_ranking_observations(
    data: list[dict],
) -> tuple[RankingObservation, ...]:
    """Parse ranking observation dicts into domain objects."""
    from datetime import UTC, datetime

    from sie.domain.models.search import SearchDevice

    observations = []
    for item in data:
        observed_at = item.get("observed_at")
        if isinstance(observed_at, str):
            observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        elif observed_at is None:
            observed_at = datetime.now(UTC)

        import contextlib

        device = SearchDevice.DESKTOP
        if "device" in item:
            with contextlib.suppress(ValueError):
                device = SearchDevice(item["device"])

        observations.append(
            RankingObservation(
                keyword=item.get("keyword", ""),
                target_url=item.get("target_url", "https://example.com/"),
                position=item.get("position", 1),
                source=item.get("source", "api"),
                search_engine=item.get("search_engine", "google"),
                country=item.get("country", "us"),
                language=item.get("language", "en"),
                device=device,
                observed_at=observed_at,
            )
        )
    return tuple(observations)


def _parse_competitor_rankings(
    data: list[dict],
) -> tuple[CompetitorRanking, ...]:
    """Parse competitor ranking dicts into domain objects."""
    from datetime import UTC, datetime

    rankings = []
    for item in data:
        observed_at = item.get("observed_at")
        if isinstance(observed_at, str):
            observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        elif observed_at is None:
            observed_at = datetime.now(UTC)

        rankings.append(
            CompetitorRanking(
                keyword=item.get("keyword", ""),
                competitor_domain=item.get("competitor_domain", ""),
                competitor_url=item.get("competitor_url", "https://example.com/"),
                position=item.get("position", 1),
                observed_at=observed_at,
            )
        )
    return tuple(rankings)
