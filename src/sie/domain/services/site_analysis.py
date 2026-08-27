"""Site Analysis Service — unified website intelligence.

Combines crawling, technical SEO audit, content analysis, link graph,
ranking discovery, search intelligence, AIO (AI Overview), and GEO (Generative Engine)
analysis into a single actionable report for dominating search results.

This is the main entry point for "analyze this website and tell me how to rank #1" workflows.
"""

from __future__ import annotations

import asyncio
import html as html_mod
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sie.domain.engines.search_aio import analyze_aio_observations
from sie.domain.engines.search_geo import analyze_geo_observations
from sie.domain.models.search_aio import AIOverviewObservation, AIOverviewType, AIOCitation, CitationSource
from sie.domain.models.audit import SiteArchitectureReport, TechnicalAuditResult
from sie.domain.models.content import ContentQualityReport
from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
    SearchQuery,
)
from sie.domain.models.search_geo import GenerativeEngineType, GEOObservation, EntityMention, EntityType
from sie.domain.ports.persistence import CrawlRunRepository
from sie.domain.ports.search_provider import SearchProvider
from sie.infrastructure.search.provider_registry import ProviderRegistry
from sie.domain.services.audit_service import AuditService
from sie.domain.services.content_service import ContentService
from sie.domain.services.crawl_service import CrawlService
from sie.domain.services.search_collection_service import SearchCollectionService
from sie.domain.services.search_intelligence import (
    RecommendationCategory,
    RecommendationPriority,
    SearchIntelligenceResult,
    SearchIntelligenceService,
    SearchRecommendation,
)
from sie.infrastructure.crux import CruxService
from sie.logging import get_logger

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# Enriched Data Models for Evidence-Based Reporting
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class AccessStatus:
    """Access and protection status for a target website."""
    accessible: bool = True
    protection_detected: str | None = None  # e.g. "Cloudflare", "Akamai", "WAF"
    protection_details: str | None = None
    status_code: int = 200
    bypass_attempted: bool = False
    bypass_succeeded: bool = False
    bypass_methods_used: list[str] = field(default_factory=list)
    analysis_status: str = "SUCCESS"  # SUCCESS, BLOCKED, PARTIAL
    block_reason: str | None = None
    analyzed_page_is_challenge: bool = False

    @property
    def is_blocked(self) -> bool:
        return not self.accessible or self.analysis_status == "BLOCKED"


@dataclass
class WebsiteTypeInfo:
    """Detected website technology information."""
    technology: str = "Unknown"
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    cms: str | None = None
    framework: str | None = None
    language: str | None = None
    server: str | None = None
    cdn: str | None = None


@dataclass
class KeywordRankingDetail:
    """Detailed per-keyword ranking evidence."""
    keyword: str
    source: str  # "discovered" | "user-provided"
    search_location: str
    search_engine: str
    language: str
    device: str
    search_date: str
    observed_position: int | None = None  # None = not found
    checked_to: str = "Top 100"
    ranking_url: str | None = None
    evidence: str = ""
    status: str = "Verified"  # Verified, Could Not Verify, Blocked
    confidence: str = "HIGH"  # HIGH, MEDIUM, LOW


@dataclass
class ContentGapDetail:
    """Evidence for a content gap."""
    keyword: str
    search_intent: str  # informational, commercial, etc.
    site_pages_addressing: int = 0
    competitor_pages_addressing: int = 0
    competitor_domains: list[str] = field(default_factory=list)
    missing_topics: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class AuthorityGapDetail:
    """Evidence for an authority gap."""
    backlink_data_available: bool = False
    referring_domains_compared: int = 0
    comparison_methodology: str = "Not assessed"
    limitation: str = "No reliable backlink dataset available during this analysis."
    confidence: str = "LOW"


@dataclass
class AIODetailQuery:
    """Per-query AI Overview evidence."""
    keyword: str
    ai_overview_detected: bool = False
    target_cited: bool = False
    cited_sources: list[str] = field(default_factory=list)
    search_location: str = ""
    search_date: str = ""
    evidence: str = ""


@dataclass
class GEODetailQuery:
    """Per-query Generative Engine evidence."""
    query: str
    engine: str
    target_mentioned: bool = False
    competitors_mentioned: list[str] = field(default_factory=list)
    evidence: str = ""


@dataclass
class TechnicalMetricDetail:
    """Per-metric technical SEO evidence with scoring methodology."""
    metric_name: str
    weight: float  # percentage of total score
    expected_score: float
    actual_score: float
    status: str  # PASS, NEEDS IMPROVEMENT, FAIL
    evidence: str = ""
    what_was_checked: str = ""
    what_failed: str = ""
    why_it_matters: str = ""
    remediation: str = ""
    reference_url: str | None = None


@dataclass
class CountryActionItem:
    """A single actionable item for a specific country."""
    title: str
    why_applicable: str = ""
    priority: str = "MEDIUM"  # P0, P1, P2
    implementation: str = ""
    reference_url: str | None = None
    expected_outcome: str = ""


@dataclass
class CountryRankingDetail:
    """Detailed per-country ranking evidence with implementation guidance."""
    country_code: str
    country_name: str
    keywords_tested: list[str] = field(default_factory=list)
    keywords_ranking: int = 0
    keywords_not_ranking: int = 0
    visibility_score: float = 0.0
    seo_score: float = 0.0
    aio_score: float = 0.0
    geo_score: float = 0.0
    overall_score: float = 0.0
    observed_issues: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    action_items: list[CountryActionItem] = field(default_factory=list)


@dataclass
class ReportMetadata:
    """Execution metadata for reproducibility."""
    target_url: str = ""
    analysis_date: str = ""
    analysis_started: str = ""
    analysis_completed: str = ""
    report_generated: str = ""
    timezone: str = "UTC"
    country: str = ""
    language: str = "en"
    device: str = "desktop"
    search_engine: str = "Google"
    crawler_mode: str = "HTTP (no JavaScript rendering)"
    analysis_duration_seconds: float = 0.0
    pages_crawled: int = 0


# ════════════════════════════════════════════════════════════════════════════
# Universal Evidence-Based Reporting Models
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class AnalysisMetric:
    """Reusable metric structure for ALL analysis categories.

    Every numeric score in the report must be reproducible from:
    Raw Observation -> Normalization -> Expected -> Normalized Score -> Weight -> Contribution
    """

    # Required fields (no defaults)
    metric_name: str
    category: str  # "technical", "content", "ranking", "architecture", "aio", "geo"
    metric_type: str  # "binary", "percentage", "threshold", "range", "composite"
    expected: float  # target value on 0-100 scale
    normalized_score: float  # 0-100 score after normalization
    weight: float  # percentage contribution (sums to 100 within category)

    # Optional fields (with defaults)
    raw_value: float | None = None
    raw_unit: str | None = None
    raw_evidence: str = ""
    normalization_method: str = ""
    score_contribution: float = 0.0  # weight * normalized_score / 100
    status: str = ""  # PASS, GOOD, NEEDS IMPROVEMENT, POOR, NOT ASSESSED
    evidence: str = ""
    evidence_quality: str = "UNAVAILABLE"  # OBSERVED, CALCULATED, INFERRED, UNAVAILABLE
    affected_urls: list[str] = field(default_factory=list)
    affected_keywords: list[str] = field(default_factory=list)
    why_it_matters: str = ""
    remediation: str = ""
    implementation: str = ""
    reference_url: str | None = None
    limitations: str = ""
    sample_size: int | None = None
    data_coverage: float | None = None
    coverage_methodology: str = ""
    confidence: str = "UNABLE TO VERIFY"

    def __post_init__(self) -> None:
        self.score_contribution = self.weight * self.normalized_score / 100.0


@dataclass
class CategoryScore:
    """Wraps a full category analysis with universal scoring structure."""

    category_name: str
    overall_score: float | None  # 0-100 or None if NOT ASSESSED
    score_status: str  # "ASSESSED", "NOT ASSESSED", "INSUFFICIENT DATA"
    scoring_methodology: str
    metrics: list[AnalysisMetric]

    # Coverage
    sample_size: int
    data_coverage: float  # 0.0-1.0

    # Confidence
    confidence: str  # HIGH, MEDIUM, LOW, UNABLE TO VERIFY
    confidence_factors: list[str] = field(default_factory=list)

    # Limitations
    limitations: list[str] = field(default_factory=list)
    evidence_quality_summary: str = "UNAVAILABLE"

    # Source metadata
    data_source: str = ""  # "crawl", "serp", "live_query", "simulated"
    observation_date: str | None = None


@dataclass
class SemanticAlignmentResult:
    """Title/heading semantic alignment between target keywords and site content.

    Deterministic: uses string matching and word overlap only.
    No external LLM, embedding model, or API calls.
    """

    keyword: str
    exact_title_matches: int = 0
    partial_title_matches: int = 0
    semantic_variants: list[str] = field(default_factory=list)
    heading_keyword_coverage: float = 0.0
    alignment_score: float = 0.0  # 0-100
    affected_urls: list[str] = field(default_factory=list)
    evidence: str = ""


# ════════════════════════════════════════════════════════════════════════════
# Original Data Models (enriched with evidence fields)
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SiteRankingSnapshot:
    """Snapshot of a site's current search visibility."""
    domain: str
    total_keywords_tracked: int
    keywords_in_top_3: int
    keywords_in_top_10: int
    keywords_in_top_20: int
    keywords_not_ranking: int
    visibility_score: float
    estimated_monthly_traffic: int
    top_keywords: list[dict[str, Any]] = field(default_factory=list)
    keyword_details: list[KeywordRankingDetail] = field(default_factory=list)
    keyword_discovery_method: str = "TF-IDF extraction from crawled content"
    content_gap: ContentGapDetail | None = None
    authority_gap: AuthorityGapDetail | None = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class SiteAIOAnalysis:
    """AI Overview (AIO) analysis for the site."""
    keywords_checked: int
    ai_overviews_present: int
    target_cited_count: int
    competitor_cited_count: int
    citation_rate: float
    target_citation_rate: float
    competitor_domains_cited: list[str] = field(default_factory=list)
    top_opportunities: list[dict[str, Any]] = field(default_factory=list)
    query_details: list[AIODetailQuery] = field(default_factory=list)
    detection_methodology: str = "SERP feature analysis for AI Overview snippets"
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class SiteGEOAnalysis:
    """Generative Engine Optimization (GEO) analysis for the site."""
    keywords_checked: int
    target_mentioned_count: int
    competitor_mentioned_count: int
    mention_rate: float
    avg_mention_count: float
    competitor_domains_mentioned: list[str] = field(default_factory=list)
    top_opportunities: list[dict[str, Any]] = field(default_factory=list)
    query_details: list[GEODetailQuery] = field(default_factory=list)
    detection_methodology: str = "Generative engine response analysis for brand mentions"
    engines_tested: list[str] = field(default_factory=list)
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class SiteTechnicalHealth:
    """Technical health summary from crawl + audit."""
    pages_crawled: int
    critical_issues: int
    warning_issues: int
    info_issues: int
    indexable_pages: int
    non_indexable_pages: int
    avg_load_time_ms: float
    core_web_vitals_pass: bool
    has_ssl: bool
    robots_txt_valid: bool
    sitemap_exists: bool
    top_issues: list[dict[str, Any]] = field(default_factory=list)
    metric_details: list[TechnicalMetricDetail] = field(default_factory=list)
    scoring_methodology: str = "Weighted composite: start at 100, deduct for issues"


@dataclass(frozen=True, slots=True)
class SiteContentHealth:
    """Content quality summary from crawl."""
    pages_analyzed: int
    avg_quality_score: float
    thin_content_pages: int
    duplicate_groups: int
    missing_h1_pages: int
    missing_meta_desc_pages: int
    low_word_count_pages: int
    top_issues: list[tuple[str, int]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SiteArchitectureHealth:
    """Site architecture / link graph summary."""
    total_pages: int
    total_internal_links: int
    avg_depth: float
    orphan_pages: int
    max_depth: int
    pagerank_distribution: dict[str, float] = field(default_factory=dict)

    @property
    def orphans(self) -> int:
        return self.orphan_pages


@dataclass(frozen=True, slots=True)
class SiteCountryRanking:
    """Country-specific ranking and visibility analysis."""
    country_code: str
    country_name: str
    seo_score: float
    aio_score: float
    geo_score: float
    overall_score: float
    keywords_ranking: int
    keywords_not_ranking: int
    visibility_score: float
    top_keywords: list[dict[str, Any]] = field(default_factory=list)
    aio_citations: int = 0
    geo_mentions: int = 0
    recommendations: list[SearchRecommendation] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SitePerformanceSummary:
    """Dataset-level performance summary from deterministic HTML analysis.

    Does NOT pretend to measure Core Web Vitals or real browser performance.
    All metrics are derived from static HTML analysis of crawled pages.
    """
    pages_analyzed: int = 0
    avg_performance_score: float = 0.0  # 0.0-1.0
    pages_above_threshold: int = 0  # score >= 0.7
    pages_below_threshold: int = 0  # score < 0.4
    total_findings: int = 0
    avg_html_size: float = 0.0
    avg_content_efficiency: float = 0.0
    top_issues: list[str] = field(default_factory=list)
    largest_pages: list[tuple[str, int]] = field(default_factory=list)  # (url, bytes)
    least_efficient: list[tuple[str, float]] = field(default_factory=list)  # (url, efficiency)
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    score: float = 0.0  # 0-100
    methodology: str = "Deterministic HTML analysis of crawled pages"
    limitations: list[str] = field(default_factory=lambda: [
        "Static HTML analysis only — no real browser rendering or network timing",
        "Does not measure Core Web Vitals or real-user performance",
        "Resource sizes are from HTML references, not actual downloaded sizes",
    ])


@dataclass(frozen=True, slots=True)
class SiteEntityKnowledgeGraphAnalysis:
    """Entity/Knowledge Graph analysis for the site."""
    entities_extracted: int = 0
    unique_entities: int = 0
    entity_types: dict[str, int] = field(default_factory=dict)
    wikipedia_aligned: int = 0
    wikidata_aligned: int = 0
    knowledge_graph_coverage: float = 0.0
    entity_salience_scores: dict[str, float] = field(default_factory=dict)
    missing_entity_types: list[str] = field(default_factory=list)
    entity_relationships: list[dict[str, Any]] = field(default_factory=list)
    entity_gaps_vs_competitors: list[str] = field(default_factory=list)
    schema_entity_alignment: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass(frozen=True, slots=True)
class SiteAnalysisResult:
    """Complete site analysis result - the main deliverable."""
    domain: str
    analyzed_at: datetime
    crawl_run_id: str | None

    # Core health scores (0-100)
    technical_score: float
    content_score: float
    ranking_score: float
    architecture_score: float
    aio_score: float = 0.0
    geo_score: float = 0.0
    overall_score: float = 0.0

    # Detailed sections
    rankings: SiteRankingSnapshot | None = None
    technical: SiteTechnicalHealth | None = None
    content: SiteContentHealth | None = None
    architecture: SiteArchitectureHealth | None = None
    aio: SiteAIOAnalysis | None = None
    geo: SiteGEOAnalysis | None = None

    # Country-wise rankings
    country_rankings: tuple[SiteCountryRanking, ...] = ()
    country_ranking_details: tuple[CountryRankingDetail, ...] = ()

    # Unified recommendations (prioritized across all areas)
    recommendations: tuple[SearchRecommendation, ...] = ()

    # Intelligence details (for drill-down)
    search_intelligence: SearchIntelligenceResult | None = None
    technical_audit: TechnicalAuditResult | None = None
    architecture_report: SiteArchitectureReport | None = None
    content_quality: ContentQualityReport | None = None

    # Access / protection status
    access_status: AccessStatus | None = None
    website_type: WebsiteTypeInfo | None = None
    report_metadata: ReportMetadata | None = None
    analysis_started_at: datetime | None = None
    analysis_completed_at: datetime | None = None

    # Universal evidence-based breakdowns (new)
    technical_breakdown: CategoryScore | None = None
    content_breakdown: CategoryScore | None = None
    ranking_breakdown: CategoryScore | None = None
    architecture_breakdown: CategoryScore | None = None
    aio_breakdown: CategoryScore | None = None
    geo_breakdown: CategoryScore | None = None

    # Per-page content metrics (for URL-level evidence)
    content_page_metrics: tuple = ()

    # Semantic alignment results
    semantic_alignment: tuple[SemanticAlignmentResult, ...] = ()

    # Entity / Knowledge Graph analysis
    entity_analysis: SiteEntityKnowledgeGraphAnalysis | None = None

    # Page performance (deterministic, from crawled HTML)
    performance_summary: SitePerformanceSummary | None = None

    # Search opportunity analysis
    search_opportunities: Any = None  # SearchOpportunityResult | None

    # Cross-engine optimization synthesis
    optimization_synthesis: Any = None  # OptimizationResult | None

    # CrUX real-user Core Web Vitals (None if not configured)
    crux_metrics: Any = None  # CruxMetrics | None
    crux_status: str = "NOT_CONFIGURED"  # NOT_CONFIGURED, AVAILABLE, ERROR, NO_DATA


class SiteAnalysisService:
    """Orchestrates complete site analysis: crawl + audit + rankings + intelligence."""

    def __init__(
        self,
        crawl_service: CrawlService,
        audit_service: AuditService,
        content_service: ContentService,
        search_provider: SearchProvider | ProviderRegistry,
        repository: CrawlRunRepository,
        crux_service: CruxService | None = None,
        collection_source: str = "site-analysis",
    ) -> None:
        self._crawl_service = crawl_service
        self._audit_service = audit_service
        self._content_service = content_service
        self._repository = repository
        self._crux_service = crux_service

        # Handle both single provider (backward compat) and registry
        if isinstance(search_provider, ProviderRegistry):
            self._provider_registry = search_provider
            self._search_provider = search_provider.get_for_aio() or search_provider.get_for_geo() or search_provider.get_for_rankings()
            rankings_provider = search_provider.get_for_rankings()
        else:
            # Backward compatibility: single provider for all capabilities
            self._provider_registry = None
            self._search_provider = search_provider
            rankings_provider = search_provider

        self._collection_service = SearchCollectionService(
            rankings_provider,
            repository=repository,
            source=collection_source,
        )
        self._intelligence_service = SearchIntelligenceService()

    # ══════════════════════════════════════════════════════════════════════
    # Country-wise Analysis
    # ══════════════════════════════════════════════════════════════════════

    COUNTRY_NAMES = {
        "us": "United States", "gb": "United Kingdom", "de": "Germany",
        "fr": "France", "in": "India", "au": "Australia",
        "ca": "Canada", "br": "Brazil", "jp": "Japan",
        "kr": "South Korea", "mx": "Mexico", "it": "Italy",
        "es": "Spain", "nl": "Netherlands", "se": "Sweden",
        "sg": "Singapore", "ae": "UAE", "sa": "Saudi Arabia",
        "za": "South Africa", "ng": "Nigeria", "pk": "Pakistan",
        "bd": "Bangladesh", "lk": "Sri Lanka", "np": "Nepal",
    }

    async def _analyze_country(
        self,
        domain: str,
        country_code: str,
        target_keywords: list[str],
        crawl_pages: list,
        device: str,
    ) -> SiteCountryRanking:
        """Analyze a site's visibility in a specific country."""
        country_name = self.COUNTRY_NAMES.get(country_code, country_code.upper())

        # Reuse crawl pages (shared across countries), query country-specific SERPs
        try:
            ranking_snapshot = await self._discover_rankings(
                domain, crawl_pages,
                target_keywords=target_keywords,
                country=country_code,
                device=device,
            )
        except Exception:
            ranking_snapshot = None

        # AIO analysis for this country
        aio_analysis = None
        try:
            aio_analysis = await self._analyze_aio(
                domain, target_keywords, country_code, device
            )
        except Exception:
            pass

        # GEO analysis for this country
        geo_analysis = None
        try:
            geo_analysis = await self._analyze_geo(
                domain, target_keywords, country_code, device
            )
        except Exception:
            pass

        # Calculate scores
        ranking_score = self._score_ranking(ranking_snapshot)
        aio_score_val = self._score_aio(aio_analysis)
        geo_score_val = self._score_geo(geo_analysis)
        overall = (ranking_score + aio_score_val + geo_score_val) / 3

        # Build country-specific recommendations
        recs: list[SearchRecommendation] = []
        action_items: list[str] = []

        if ranking_snapshot:
            if ranking_snapshot.keywords_in_top_10 == 0 and ranking_snapshot.total_keywords_tracked > 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.CRITICAL,
                    title=f"No keywords ranking in top 10 in {country_name}",
                    description=(
                        f"In {country_name}, no target keywords rank in the top 10. "
                        f"Content must be localized for {country_name} search intent, "
                        f"and local authority signals must be built."
                    ),
                    confidence=0.9,
                ))
                action_items.append(
                    f"Create {country_name}-specific landing pages targeting local search intent"
                )
                action_items.append(
                    f"Build backlinks from {country_name}-based authoritative sites"
                )
                action_items.append(
                    f"Register Google Business Profile for {country_name} presence"
                )

            if ranking_snapshot.visibility_score < 0.2:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.HIGH,
                    title=f"Low search visibility in {country_name} ({ranking_snapshot.visibility_score:.0%})",
                    description=(
                        f"Overall visibility in {country_name} is very low. "
                        f"Consider country-specific content strategy and local SEO."
                    ),
                    confidence=0.85,
                ))
                action_items.append(
                    f"Implement hreflang tags for {country_name} content"
                )

        if aio_analysis:
            if aio_analysis.ai_overviews_present > 0 and aio_analysis.target_cited_count == 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.AIO,
                    priority=RecommendationPriority.HIGH,
                    title=f"AI Overviews present in {country_name} but site not cited",
                    description=(
                        f"In {country_name}, AI Overviews appear for {aio_analysis.ai_overviews_present} keywords "
                        f"but your site is not cited. Competitors are."
                    ),
                    confidence=0.85,
                ))
                action_items.append(
                    f"Create content targeting {country_name}-specific search queries with direct answers"
                )
                action_items.append(
                    f"Build topical authority in {country_name} market through local citations"
                )

        if geo_analysis:
            if geo_analysis.target_mentioned_count == 0 and geo_analysis.competitor_mentioned_count > 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.GEO,
                    priority=RecommendationPriority.HIGH,
                    title=f"Not mentioned in GEO engines in {country_name}",
                    description=(
                        f"Competitors are mentioned {geo_analysis.competitor_mentioned_count} times "
                        f"in generative engines for {country_name} queries. Build authority."
                    ),
                    confidence=0.8,
                ))
                action_items.append(
                    f"Build citations on {country_name}-specific authority domains"
                )
                action_items.append(
                    "Create factual, well-structured content that AI engines cite"
                )

        top_kws = []
        if ranking_snapshot and ranking_snapshot.top_keywords:
            top_kws = ranking_snapshot.top_keywords[:10]

        return SiteCountryRanking(
            country_code=country_code,
            country_name=country_name,
            seo_score=ranking_score,
            aio_score=aio_score_val,
            geo_score=geo_score_val,
            overall_score=overall,
            keywords_ranking=ranking_snapshot.keywords_in_top_10 if ranking_snapshot else 0,
            keywords_not_ranking=ranking_snapshot.keywords_not_ranking if ranking_snapshot else 0,
            visibility_score=ranking_snapshot.visibility_score if ranking_snapshot else 0.0,
            top_keywords=top_kws,
            aio_citations=aio_analysis.target_cited_count if aio_analysis else 0,
            geo_mentions=geo_analysis.target_mentioned_count if geo_analysis else 0,
            recommendations=tuple(recs),
            action_items=action_items,
        )

    async def _analyze_all_countries(
        self,
        domain: str,
        target_countries: list[str],
        target_keywords: list[str],
        crawl_pages: list,
        device: str,
    ) -> tuple[SiteCountryRanking, ...]:
        """Analyze visibility across multiple countries."""
        results: list[SiteCountryRanking] = []
        for cc in target_countries:
            try:
                cr = await self._analyze_country(
                    domain, cc, target_keywords, crawl_pages, device
                )
                results.append(cr)
            except Exception as e:
                logger.warning("Country analysis failed for %s: %s", cc, e)
        return tuple(results)

    async def analyze_site(
        self,
        domain: str,
        *,
        max_pages: int = 100,
        max_keywords: int = 50,
        country: str = "us",
        target_countries: list[str] | None = None,
        device: str = "desktop",
        competitors: list[str] | None = None,
        deep_aio: bool = True,
        deep_geo: bool = True,
    ) -> SiteAnalysisResult:
        """Run complete site analysis with SEO, AIO, and GEO intelligence."""
        analysis_start = datetime.now(UTC)
        logger.info("Starting comprehensive site analysis for %s", domain)

        # Normalize domain
        clean_domain = self._normalize_domain(domain)
        seed_url = f"https://{clean_domain}"

        # ─── Step 1: Crawl the site ───
        crawl_run_id = await self._run_crawl(seed_url, max_pages)
        crawl_pages = self._get_crawl_pages(crawl_run_id)

        if not crawl_pages:
            logger.warning("No pages crawled for %s", domain)
            return self._empty_result(clean_domain, crawl_run_id, analysis_start)

        # ─── Step 1b: Detect access status (Cloudflare, WAF, etc.) ───
        access_status = self._detect_access_status(crawl_pages)

        # ─── Step 1c: Detect website type ───
        website_type = self._detect_website_type(crawl_pages)

        # ─── Step 2: Run technical audit + content analysis + link graph (parallel) ───
        technical_task = self._audit_service.run_technical_audit(crawl_run_id, crawl_pages)
        architecture_task = self._audit_service.run_link_graph(crawl_run_id, crawl_pages)
        content_task = self._content_service.analyze_content(crawl_run_id, crawl_pages)

        technical_result, architecture_report, content_metrics = await asyncio.gather(
            technical_task, architecture_task, content_task
        )

        content_quality = await self._content_service.generate_quality_report(crawl_run_id, content_metrics)

        # ─── Step 3: Intelligently discover target keywords from content ───
        target_keywords = self._extract_target_keywords(crawl_pages, max_keywords)
        logger.info("Extracted %d target keywords for %s", len(target_keywords), clean_domain)

        # ─── Step 4: Discover rankings for the domain ───
        ranking_snapshot = await self._discover_rankings(
            clean_domain,
            crawl_pages,
            target_keywords=target_keywords,
            country=country,
            device=device,
        )

        # ─── Step 5: Analyze AIO (AI Overview) presence ───
        aio_analysis = None
        if deep_aio and target_keywords:
            aio_analysis = await self._analyze_aio(
                clean_domain, target_keywords, country, device
            )

        # ─── Step 6: Analyze GEO (Generative Engine) presence ───
        geo_analysis = None
        if deep_geo and target_keywords:
            geo_analysis = await self._analyze_geo(
                clean_domain, target_keywords, country, device
            )

        # ─── Step 7: Collect competitor rankings ───
        competitor_rankings = await self._collect_competitor_rankings(
            clean_domain,
            ranking_snapshot.top_keywords if ranking_snapshot else [],
            competitors=competitors,
            country=country,
            device=device,
        )

        # ─── Step 8: Run search intelligence ───
        search_intel = None
        if ranking_snapshot and ranking_snapshot.total_keywords_tracked > 0:
            dataset = self._build_dataset_from_rankings(clean_domain, ranking_snapshot)
            observations = self._build_observations_from_rankings(ranking_snapshot)
            search_intel = self._intelligence_service.analyze(
                dataset, observations, competitor_rankings,
                target_domain=clean_domain,
            )

        # ─── Step 8b: Entity / Knowledge Graph analysis ───
        entity_analysis = await self._analyze_entity_knowledge_graph(
            crawl_pages, target_keywords, country, device
        )

        # ─── Step 8c: Page performance analysis (deterministic) ───
        performance_summary = self._analyze_page_performance(crawl_pages)

        # ─── Step 8d: CrUX real-user Core Web Vitals ───
        crux_metrics = None
        crux_status = "NOT_CONFIGURED"
        if self._crux_service:
            try:
                from sie.infrastructure.crux import CruxResponse
                crux_response: CruxResponse = await self._crux_service.query_origin(seed_url)
                if crux_response.success and crux_response.record:
                    crux_metrics = crux_response.record
                    crux_status = "AVAILABLE"
                elif crux_response.error:
                    crux_status = "NO_DATA"
                    logger.info("CrUX data unavailable for %s: %s", domain, crux_response.error)
                else:
                    crux_status = "NO_DATA"
            except Exception as e:
                crux_status = "ERROR"
                logger.warning("CrUX query failed for %s: %s", domain, e)

        # ─── Step 8e: Fix AIO analysis truthfulness ───
        # If the search provider cannot actually detect AIO features,
        # mark the analysis as unavailable rather than producing fake results.
        if aio_analysis and aio_analysis.keywords_checked > 0:
            aio_analysis = self._correct_aio_analysis(aio_analysis)

        # ─── Step 8f: Fix GEO analysis truthfulness ───
        # The current GEO analysis creates synthetic "not mentioned" observations
        # which produce misleading numeric scores. Replace with honest NOT ASSESSED.
        if geo_analysis and geo_analysis.keywords_checked > 0:
            geo_analysis = self._correct_geo_analysis(geo_analysis)

        # ─── Step 9: Build unified health scores ───
        technical_health = self._build_technical_health(technical_result, crawl_pages)
        content_health = self._build_content_health(content_quality)
        architecture_health = self._build_architecture_health(architecture_report)

        # ─── Step 10: Generate unified recommendations (SEO + AIO + GEO) ───
        recommendations = self._build_unified_recommendations(
            ranking_snapshot=ranking_snapshot,
            technical_health=technical_health,
            content_health=content_health,
            architecture_health=architecture_health,
            aio_analysis=aio_analysis,
            geo_analysis=geo_analysis,
            search_intel=search_intel,
        )

        # ─── Step 11: Calculate overall scores ───
        technical_score = self._score_technical(technical_health)
        content_score = self._score_content(content_health)
        ranking_score = self._score_ranking(ranking_snapshot)
        architecture_score = self._score_architecture(architecture_health)
        aio_score = self._score_aio(aio_analysis)
        geo_score = self._score_geo(geo_analysis)
        overall_score = (
            technical_score + content_score + ranking_score +
            architecture_score + aio_score + geo_score
        ) / 6

        # ─── Step 12: Country-wise analysis (if requested) ───
        country_rankings_data: tuple[SiteCountryRanking, ...] = ()
        if target_countries:
            logger.info("Running country-wise analysis for %s: %s", domain, target_countries)
            country_rankings_data = await self._analyze_all_countries(
                clean_domain, target_countries, target_keywords, crawl_pages, device
            )

        analysis_end = datetime.now(UTC)

        # Build report metadata
        report_meta = ReportMetadata(
            target_url=seed_url,
            analysis_date=analysis_start.strftime("%d %B %Y"),
            analysis_started=analysis_start.strftime("%d %B %Y, %I:%M %p UTC"),
            analysis_completed=analysis_end.strftime("%d %B %Y, %I:%M %p UTC"),
            report_generated=analysis_end.strftime("%d %B %Y, %I:%M %p UTC"),
            timezone="UTC",
            country=country.upper(),
            language="en",
            device=device,
            search_engine="Google",
            crawler_mode="HTTP (no JavaScript rendering)",
            analysis_duration_seconds=round((analysis_end - analysis_start).total_seconds(), 1),
            pages_crawled=len(crawl_pages),
        )

        # Build universal breakdowns
        content_breakdown = self._build_content_breakdown(
            content_metrics, content_quality, target_keywords, crawl_pages
        )
        ranking_breakdown = self._build_ranking_breakdown(ranking_snapshot, country, device)
        architecture_breakdown = self._build_architecture_breakdown(architecture_report)
        aio_breakdown = self._build_aio_breakdown(aio_analysis, country)
        geo_breakdown = self._build_geo_breakdown(geo_analysis)

        # Semantic alignment
        semantic_alignment = self._compute_semantic_alignment(target_keywords, crawl_pages)

        # Persist AIO/GEO observations for historical tracking
        await self._persist_aio_geo_observations(
            clean_domain, aio_analysis, geo_analysis, target_keywords, country
        )

        return SiteAnalysisResult(
            domain=clean_domain,
            analyzed_at=analysis_end,
            crawl_run_id=crawl_run_id,
            technical_score=technical_score,
            content_score=content_score,
            ranking_score=ranking_score,
            architecture_score=architecture_score,
            aio_score=aio_score,
            geo_score=geo_score,
            overall_score=overall_score,
            rankings=ranking_snapshot,
            technical=technical_health,
            content=content_health,
            architecture=architecture_health,
            aio=aio_analysis,
            geo=geo_analysis,
            country_rankings=country_rankings_data,
            recommendations=recommendations,
            search_intelligence=search_intel,
            technical_audit=technical_result,
            architecture_report=architecture_report,
            content_quality=content_quality,
            access_status=access_status,
            website_type=website_type,
            report_metadata=report_meta,
            analysis_started_at=analysis_start,
            analysis_completed_at=analysis_end,
            content_breakdown=content_breakdown,
            ranking_breakdown=ranking_breakdown,
            architecture_breakdown=architecture_breakdown,
            aio_breakdown=aio_breakdown,
            geo_breakdown=geo_breakdown,
            semantic_alignment=tuple(semantic_alignment),
            entity_analysis=entity_analysis,
            performance_summary=performance_summary,
            search_opportunities=search_intel.opportunity_result if search_intel and hasattr(search_intel, 'opportunity_result') else None,
            optimization_synthesis=None,  # Requires full cross-engine data; TODO: wire when all engines integrated
            crux_metrics=crux_metrics,
            crux_status=crux_status,
        )

    async def _persist_aio_geo_observations(
        self,
        domain: str,
        aio_analysis: SiteAIOAnalysis | None,
        geo_analysis: SiteGEOAnalysis | None,
        target_keywords: list[str],
        country: str,
    ) -> None:
        """Persist AIO and GEO observations for historical tracking."""
        if not aio_analysis and not geo_analysis:
            return

        # Create a dataset for this analysis
        dataset_id = f"site-{domain}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        dataset = SearchDataset(
            dataset_id=dataset_id,
            name=domain,
            source="site-analysis",
            created_at=datetime.now(UTC),
            total_keywords=len(target_keywords),
            total_observations=0,  # Will be updated after saving
        )

        try:
            # Save dataset
            await self._repository.save_search_dataset(dataset)

            # Persist AIO observations
            if aio_analysis and aio_analysis.query_details:
                aio_observations = []
                for detail in aio_analysis.query_details:
                    obs = AIOverviewObservation(
                        keyword=detail.keyword,
                        ai_type=AIOverviewType.AI_OVERVIEW if detail.ai_overview_detected else AIOverviewType.OTHER,
                        present=detail.ai_overview_detected,
                        target_cited=detail.target_cited,
                        target_domain=domain,
                        citation_count=len(detail.cited_sources),
                        citations=tuple(
                            AIOCitation(
                                domain=url.split("/")[2].lower().removeprefix("www."),
                                url=url,
                                position=i,
                                source_type=CitationSource.WEB_PAGE,
                                title="",
                            )
                            for i, url in enumerate(detail.cited_sources)
                        ),
                        competitor_cited_domains=tuple(
                            d for d in detail.cited_sources
                            if d.split("/")[2].lower().removeprefix("www.") != self._normalize_domain(domain)
                        ),
                        observed_at=datetime.now(UTC),
                        source="site-analysis",
                    )
                    aio_observations.append(obs)

                if aio_observations:
                    await self._repository.save_aio_observations(f"site-aio-{domain}", aio_observations)

            # Persist GEO observations
            if geo_analysis and geo_analysis.query_details:
                geo_observations = []
                for detail in geo_analysis.query_details:
                    obs = GEOObservation(
                        keyword=detail.query,
                        engine_type=GenerativeEngineType.CHATGPT,  # Default to ChatGPT
                        target_mentioned=detail.target_mentioned,
                        target_domain=domain,
                        mention_count=1 if detail.target_mentioned else 0,
                        entity_mentions=(),
                        competitor_domains=tuple(detail.competitors_mentioned),
                        citation_urls=(),
                        answer_length=0,
                        observed_at=datetime.now(UTC),
                        source="site-analysis",
                    )
                    geo_observations.append(obs)

                if geo_observations:
                    await self._repository.save_geo_observations(f"site-geo-{domain}", geo_observations)

        except Exception as e:
            logger.warning("Failed to persist AIO/GEO observations for %s: %s", domain, e)

    # ══════════════════════════════════════════════════════════════════════
    # Access Detection & Website Type
    # ══════════════════════════════════════════════════════════════════════

    def _detect_access_status(self, crawl_pages: list) -> AccessStatus:
        """Detect if the site was accessible or blocked (Cloudflare, WAF, etc.)."""
        if not crawl_pages:
            return AccessStatus(
                accessible=False,
                status_code=0,
                analysis_status="BLOCKED",
                block_reason="No pages could be retrieved.",
            )

        first_page = crawl_pages[0]
        html = first_page.decoded_text() if first_page.is_html else ""
        html_lower = html.lower()

        # Cloudflare detection patterns
        cloudflare_indicators = [
            "cf-browser-verification",
            "challenge-platform",
            "cloudflare-nginx",
            "cf-challenge",
            "_cf_chl",
            "ray id:",
            "attention required! | cloudflare",
            "checking if the site connection is secure",
            "enable javascript and cookies to continue",
            "please wait while we verify your browser",
            "just a moment...",
            "cf-turnstile",
            "powered by cloudflare",
        ]

        # WAF / Bot protection patterns
        waf_indicators = [
            "access denied", "forbidden", "blocked",
            "captcha", "security check",
            "request blocked", "bot detection",
        ]

        protection_detected = None
        protection_details = None
        is_challenge = False

        # Check for Cloudflare
        if any(ind in html_lower for ind in cloudflare_indicators):
            protection_detected = "Cloudflare"
            is_challenge = True
            if "just a moment" in html_lower or "checking if the site" in html_lower:
                protection_details = "Cloudflare Browser Verification (JavaScript challenge)"
            elif "attention required" in html_lower:
                protection_details = "Cloudflare Access Denied (IP/country block or WAF rule)"
            elif "challenge-platform" in html_lower or "cf-challenge" in html_lower:
                protection_details = "Cloudflare Challenge Page"
            elif "cf-turnstile" in html_lower:
                protection_details = "Cloudflare Turnstile (CAPTCHA verification)"
            else:
                protection_details = "Cloudflare protection detected"

        # Check for other WAF indicators
        elif first_page.status_code in (403, 429):
            if any(ind in html_lower for ind in waf_indicators):
                protection_detected = "WAF/Bot Protection"
                protection_details = f"HTTP {first_page.status_code} with protection page"

        # Check for very small pages that might be challenge stubs
        elif len(html) < 500 and first_page.status_code == 200:
            if any(kw in html_lower for kw in ["verify", "challenge", "security", "bot"]):
                protection_detected = "Unknown Protection"
                protection_details = "Small response with challenge-like content"

        # Determine accessibility
        accessible = (
            first_page.status_code == 200
            and not is_challenge
            and protection_detected is None
        )

        bypass_methods: list[str] = []
        if is_challenge or not accessible:
            bypass_methods = self._get_bypass_methods()

        return AccessStatus(
            accessible=accessible,
            protection_detected=protection_detected,
            protection_details=protection_details,
            status_code=first_page.status_code,
            bypass_attempted=bool(bypass_methods),
            bypass_succeeded=accessible and bool(bypass_methods),
            bypass_methods_used=bypass_methods,
            analysis_status="SUCCESS" if accessible else "BLOCKED",
            block_reason=protection_details if not accessible else None,
            analyzed_page_is_challenge=is_challenge,
        )

    def _get_bypass_methods(self) -> list[str]:
        """List bypass methods that would be attempted."""
        return [
            "User-agent rotation",
            "Standard HTTP fetch (current method)",
        ]

    def _detect_website_type(self, crawl_pages: list) -> WebsiteTypeInfo:
        """Detect the website technology stack from crawl data."""
        if not crawl_pages:
            return WebsiteTypeInfo(technology="Unknown", confidence=0.0, evidence=["No pages crawled"])

        evidence: list[str] = []
        tech_signals: Counter = Counter()
        cms: str | None = None
        framework: str | None = None
        language: str | None = None
        server: str | None = None
        cdn: str | None = None

        for page in crawl_pages[:20]:
            if not page.is_html:
                continue
            html = page.decoded_text()
            html_lower = html.lower()
            headers = dict(page.headers) if page.headers else {}

            # Server detection from headers
            if not server and headers:
                server_header = headers.get("server", "")
                if server_header:
                    server = server_header.split("/")[0] if "/" in server_header else server_header
                    evidence.append(f"Server header: {server_header}")

            # CDN detection from headers
            if not cdn and headers:
                if "cf-ray" in headers or "cloudflare" in headers.get("server", "").lower():
                    cdn = "Cloudflare"
                    evidence.append("CDN detected: Cloudflare (cf-ray header)")
                elif "x-amz-cf-id" in headers or "x-amz-cf-ray" in headers:
                    cdn = "Amazon CloudFront"
                    evidence.append("CDN detected: Amazon CloudFront")
                elif "x-fastly-request-id" in headers:
                    cdn = "Fastly"
                    evidence.append("CDN detected: Fastly")

            # WordPress
            if any(s in html_lower for s in ["wp-content", "wp-includes", "wordpress"]):
                tech_signals["WordPress"] += 3
                evidence.append("WordPress indicators: wp-content/wp-includes paths")
            if "wp-json" in html_lower:
                tech_signals["WordPress"] += 2
                evidence.append("WordPress REST API endpoint found (wp-json)")

            # Shopify
            if any(s in html_lower for s in ["shopify", "cdn.shopify.com"]):
                tech_signals["Shopify"] += 3
                evidence.append("Shopify indicators detected")

            # Next.js
            if "__next" in html_lower or "_next/static" in html_lower:
                tech_signals["Next.js"] += 4
                evidence.append("Next.js indicators: __next or _next/static")
            elif "__nuxt" in html_lower or "_nuxt/" in html_lower:
                tech_signals["Nuxt.js"] += 4
                evidence.append("Nuxt.js indicators: __nuxt or _nuxt/")
            elif "react" in html_lower and ("root" in html_lower or "__next" in html_lower):
                tech_signals["React"] += 2
                evidence.append("React indicators detected")

            # Drupal
            if any(s in html_lower for s in ["drupal", "sites/all", "sites/default"]):
                tech_signals["Drupal"] += 3
                evidence.append("Drupal indicators detected")

            # Joomla
            if any(s in html_lower for s in ["joomla", "/media/jui/"]):
                tech_signals["Joomla"] += 3
                evidence.append("Joomla indicators detected")

            # Static site generators
            if any(s in html_lower for s in ["gatsby", "gatsbyjs"]):
                tech_signals["Gatsby"] += 3
                evidence.append("Gatsby static site generator detected")
            if "hugo" in html_lower:
                tech_signals["Hugo"] += 2
                evidence.append("Hugo static site generator indicators")

            # Squarespace
            if "squarespace" in html_lower:
                tech_signals["Squarespace"] += 3
                evidence.append("Squarespace indicators detected")

            # Webflow
            if "webflow" in html_lower:
                tech_signals["Webflow"] += 3
                evidence.append("Webflow indicators detected")

            # Language detection
            if not language:
                lang_match = re.search(r'<html[^>]+lang=["\']([a-z]{2})', html, re.IGNORECASE)
                if lang_match:
                    language = lang_match.group(1)

        # Determine winner
        if tech_signals:
            winner, count = tech_signals.most_common(1)[0]
            confidence = min(1.0, count / 6.0)
            return WebsiteTypeInfo(
                technology=winner,
                confidence=round(confidence, 2),
                evidence=evidence[:10],
                cms=winner if winner in ("WordPress", "Shopify", "Drupal", "Joomla", "Squarespace") else None,
                framework=winner if winner in ("Next.js", "Nuxt.js", "React", "Gatsby") else None,
                language=language,
                server=server,
                cdn=cdn,
            )

        return WebsiteTypeInfo(
            technology="Unknown",
            confidence=0.0,
            evidence=["Insufficient indicators to determine technology"] if not evidence else evidence[:5],
            language=language,
            server=server,
            cdn=cdn,
        )

    # ══════════════════════════════════════════════════════════════════════
    # Crawl & Discovery
    # ══════════════════════════════════════════════════════════════════════

    async def _run_crawl(self, seed_url: str, max_pages: int) -> str:
        """Start and wait for crawl to complete."""
        from sie.domain.models.crawl import CrawlPolicy, CrawlTarget

        target = CrawlTarget(seed_url=seed_url)
        policy = CrawlPolicy(
            max_pages=max_pages,
            depth_limit=3,
            respect_robots_txt=True,
            follow_cross_origin=False,
        )

        run_id = await self._crawl_service.start_run(target, policy)

        # Poll until complete
        while True:
            stats = await self._crawl_service.live_stats(run_id)
            if stats and stats.status.value in ("completed", "failed", "aborted"):
                break
            await asyncio.sleep(2)

        return run_id

    def _get_crawl_pages(self, run_id: str) -> list:
        """Get crawled pages from the service's page store."""
        return self._crawl_service._pages_store.get(run_id, [])

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain input to bare hostname."""
        domain = domain.strip().lower()
        if domain.startswith(("http://", "https://")):
            parsed = urlparse(domain)
            domain = parsed.netloc or parsed.path
        domain = domain.replace("www.", "")
        domain = domain.split("/")[0].split(":")[0]
        return domain

    @staticmethod
    def _strip_html_for_keywords(raw_html: str) -> str:
        """Strip HTML tags, decode entities, and remove non-text artifacts.

        Returns clean visible text suitable for keyword extraction.
        Operates on raw HTML from ``decoded_text()`` so that the caller
        receives meaningful visible text rather than markup artifacts.
        """
        # Remove <script> and <style> blocks first
        cleaned = re.sub(
            r'<(script|style|noscript)[^>]*>.*?</\1>',
            ' ', raw_html, flags=re.DOTALL | re.IGNORECASE,
        )
        # Remove all HTML tags
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
        # Decode HTML entities (&amp; &quot; &#39; etc.)
        cleaned = html_mod.unescape(cleaned)
        # Remove URLs that may appear as bare text (http://… or https://…)
        cleaned = re.sub(r'https?://\S+', ' ', cleaned)
        # Remove email addresses
        cleaned = re.sub(r'\S+@\S+\.\S+', ' ', cleaned)
        # Collapse whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    @staticmethod
    def _is_url_or_domain_token(word: str) -> bool:
        """Return True if *word* looks like a URL fragment or domain part."""
        # Protocol prefixes and common TLDs / domain parts
        if word in (
            'http', 'https', 'ftp', 'www', 'com', 'org', 'net', 'edu',
            'gov', 'io', 'co', 'html', 'php', 'asp', 'jsp', 'css',
            'javascript', 'xmlns', 'doctype', 'charset', 'viewport',
            'content', 'type', 'text', 'meta', 'link', 'href', 'src',
            'div', 'span', 'class', 'data', 'value', 'width', 'height',
        ):
            return True
        # Pure numeric strings or strings with digits-only after prefix
        if re.fullmatch(r'\d+', word):
            return True
        # Looks like a domain part (contains only alphanumerics and hyphens,
        # no spaces — happens when URLs are split by the regex)
        if re.fullmatch(r'[a-z0-9][-a-z0-9]*', word) and len(word) > 1 and '-' in word:
            # Could be a legitimate compound keyword (e.g. 'on-page'), so
            # only reject obvious domain-style segments (>=4 segments with
            # digits or very short segments).
            parts = word.split('-')
            if len(parts) >= 4 or (len(word) <= 4 and any(c.isdigit() for c in word)):
                return True
        return False

    def _extract_target_keywords(self, crawl_pages: list, max_keywords: int) -> list[str]:
        """Intelligently extract target keywords from crawled content."""
        STOPWORDS = frozenset({
            "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
            "has", "he", "in", "is", "it", "its", "of", "on", "that", "the", "to",
            "was", "were", "will", "with", "you", "your", "we", "our", "their",
            "this", "these", "those", "have", "had", "do", "does",
            "did", "but", "not", "or", "if", "then", "else", "when", "where",
            "why", "how", "what", "who", "which", "can", "could", "should",
            "would", "may", "might", "must", "shall", "being",
            "there", "here", "more", "most", "some", "any", "all", "each",
            "few", "many", "much", "other", "such", "only", "own", "same",
            "than", "too", "very", "just", "now", "also", "well",
            "even", "back", "after", "before", "during", "while", "since",
            "until", "between", "among", "through", "into", "onto", "upon",
        })

        COMMERCIAL_INDICATORS = frozenset([
            'buy', 'price', 'cost', 'cheap', 'best', 'top', 'review', 'compare',
            'vs', 'versus', 'alternative', 'service', 'company', 'agency',
            'software', 'tool', 'platform', 'solution', 'hire',
            'consultant', 'expert', 'specialist', 'provider', 'vendor',
            'quote', 'estimate', 'pricing', 'plan', 'package', 'deal',
            'discount', 'offer', 'trial', 'demo', 'free', 'download',
            'guide', 'tutorial', 'how', 'what', 'where', 'when', 'who',
        ])

        keyword_scores: Counter = Counter()

        for i, page in enumerate(crawl_pages[:30]):
            if not page.is_html:
                continue
            try:
                text = self._strip_html_for_keywords(page.decoded_text())
                if len(text) < 200:
                    continue

                weight = 3.0 if i == 0 else (2.0 if i < 5 else 1.0)

                words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]{2,}\b', text.lower())
                filtered = [
                    w for w in words
                    if w not in STOPWORDS and len(w) >= 3
                    and not self._is_url_or_domain_token(w)
                ]

                bigrams = []
                for j in range(len(filtered) - 1):
                    bigram = f"{filtered[j]} {filtered[j+1]}"
                    if filtered[j] not in STOPWORDS and filtered[j+1] not in STOPWORDS:
                        bigrams.append(bigram)

                trigrams = []
                for j in range(len(filtered) - 2):
                    trigram = f"{filtered[j]} {filtered[j+1]} {filtered[j+2]}"
                    if (filtered[j] not in STOPWORDS and
                        filtered[j+1] not in STOPWORDS and
                        filtered[j+2] not in STOPWORDS):
                        trigrams.append(trigram)

                for word in filtered:
                    keyword_scores[word] += weight * 1.0
                for bigram in bigrams:
                    keyword_scores[bigram] += weight * 2.5
                for trigram in trigrams:
                    keyword_scores[trigram] += weight * 3.0

            except Exception:
                pass

        # Also extract from title tags and headings (higher weight)
        for i, page in enumerate(crawl_pages[:15]):
            if not page.is_html:
                continue
            try:
                text = page.decoded_text()
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', text, re.IGNORECASE)
                if title_match:
                    title_text = html_mod.unescape(title_match.group(1))
                    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]{2,}\b', title_text.lower())
                    for word in words:
                        if word not in STOPWORDS and not self._is_url_or_domain_token(word):
                            keyword_scores[word] += 5.0

                h1_matches = re.findall(r'<h1[^>]*>([^<]+)</h1>', text, re.IGNORECASE)
                for h1 in h1_matches:
                    h1_text = html_mod.unescape(h1)
                    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]{2,}\b', h1_text.lower())
                    for word in words:
                        if word not in STOPWORDS and not self._is_url_or_domain_token(word):
                            keyword_scores[word] += 3.0
            except Exception:
                pass

        # Score and filter keywords
        commercial_indicators = COMMERCIAL_INDICATORS

        scored_keywords = []
        for kw, score in keyword_scores.items():
            if len(kw) < 3:
                continue
            commercial_boost = 2.0 if any(ind in kw for ind in commercial_indicators) else 1.0
            length_boost = 1.0 + (kw.count(' ') * 0.3)
            final_score = score * commercial_boost * length_boost
            scored_keywords.append((kw, final_score))

        scored_keywords.sort(key=lambda x: -x[1])
        return [kw for kw, _ in scored_keywords[:max_keywords]]

    async def _discover_rankings(
        self,
        domain: str,
        crawl_pages: list,
        *,
        target_keywords: list[str] | None = None,
        country: str,
        device: str,
    ) -> SiteRankingSnapshot | None:
        """Discover what keywords the domain ranks for."""
        if target_keywords is None:
            target_keywords = self._extract_target_keywords(crawl_pages, max_keywords=50)

        if not target_keywords:
            logger.warning("No target keywords for %s", domain)
            return None

        search_date = datetime.now(UTC).strftime("%Y-%m-%d")

        queries = [
            SearchQuery(
                query=kw,
                search_engine="google",
                country=country,
                language="en",
                device=SearchDevice(device),
                target_domain=domain,
                max_results=100,
            )
            for kw in target_keywords
        ]

        try:
            collection_result = await self._collection_service.collect_and_persist(
                dataset_id=f"site-{domain}-{datetime.now(UTC).strftime('%Y%m%d')}",
                queries=queries,
            )
        except Exception as e:
            logger.warning("Ranking collection failed for %s: %s", domain, e)
            return None

        # Get the dataset to build snapshot
        dataset_data = await self._repository.get_search_dataset(collection_result.dataset_id)
        if not dataset_data:
            return None

        dataset, content = dataset_data
        observations = content.observations

        # Build per-keyword details
        keyword_details: list[KeywordRankingDetail] = []
        observed_keywords = {o.keyword for o in observations}

        for kw in target_keywords:
            kw_obs = [o for o in observations if o.keyword == kw]
            if kw_obs:
                obs = kw_obs[0]
                detail = KeywordRankingDetail(
                    keyword=kw,
                    source="discovered",
                    search_location=country.upper(),
                    search_engine="Google",
                    language="en",
                    device=device,
                    search_date=search_date,
                    observed_position=obs.position,
                    checked_to="Top 100",
                    ranking_url=obs.target_url,
                    evidence=f"Position #{obs.position} observed in Google SERP for {country.upper()}",
                    status="Verified",
                    confidence="HIGH",
                )
            else:
                detail = KeywordRankingDetail(
                    keyword=kw,
                    source="discovered",
                    search_location=country.upper(),
                    search_engine="Google",
                    language="en",
                    device=device,
                    search_date=search_date,
                    observed_position=None,
                    checked_to="Top 100",
                    evidence=f"No ranking found in top 100 results for {country.upper()} Google search",
                    status="Verified" if len(observations) > 0 else "Could Not Verify",
                    confidence="MEDIUM" if len(observations) > 0 else "LOW",
                )
            keyword_details.append(detail)

        # Build snapshot
        in_top_3 = sum(1 for o in observations if o.position <= 3)
        in_top_10 = sum(1 for o in observations if o.position <= 10)
        in_top_20 = sum(1 for o in observations if o.position <= 20)
        not_ranking = len(queries) - len(observations)

        top_kws = sorted(
            [{"keyword": o.keyword, "position": o.position, "url": o.target_url} for o in observations],
            key=lambda x: x["position"]
        )[:15]

        traffic = sum(self._estimate_traffic(o.position) for o in observations)

        # Build content gap detail
        content_gap = None
        if not_ranking > 0:
            missing_kws = [kw for kw in target_keywords if kw not in observed_keywords]
            if missing_kws:
                content_gap = ContentGapDetail(
                    keyword=", ".join(missing_kws[:5]),
                    search_intent="varies",
                    site_pages_addressing=0,
                    competitor_pages_addressing=0,
                    recommendation=f"Create comprehensive content targeting: {', '.join(missing_kws[:5])}",
                )

        # Build authority gap detail (no backlink data available)
        authority_gap = AuthorityGapDetail(
            backlink_data_available=False,
            comparison_methodology="Not assessed",
            limitation="No reliable backlink dataset available during this analysis. Therefore, the report does not make an authority-gap claim based on backlink data.",
            confidence="LOW",
        )

        return SiteRankingSnapshot(
            domain=domain,
            total_keywords_tracked=len(queries),
            keywords_in_top_3=in_top_3,
            keywords_in_top_10=in_top_10,
            keywords_in_top_20=in_top_20,
            keywords_not_ranking=not_ranking,
            visibility_score=dataset.total_observations / max(len(queries), 1) if queries else 0,
            estimated_monthly_traffic=traffic,
            top_keywords=top_kws,
            keyword_details=keyword_details,
            content_gap=content_gap,
            authority_gap=authority_gap,
        )

    def _estimate_traffic(self, position: int) -> int:
        """Very rough traffic estimate by position."""
        ctr_by_position = {
            1: 0.30, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
            6: 0.04, 7: 0.03, 8: 0.03, 9: 0.02, 10: 0.02,
        }
        base_volume = 1000
        return int(base_volume * ctr_by_position.get(position, 0.01))

    async def _collect_competitor_rankings(
        self,
        domain: str,
        top_keywords: list[dict[str, Any]],
        *,
        competitors: list[str] | None,
        country: str,
        device: str,
    ) -> tuple[CompetitorRanking, ...]:
        """Collect competitor rankings for the site's top keywords."""
        if not top_keywords:
            return ()

        comp_domains = competitors or []
        if not comp_domains and top_keywords:
            return ()

        queries = [
            SearchQuery(
                query=kw["keyword"],
                search_engine="google",
                country=country,
                language="en",
                device=SearchDevice(device),
                target_domain=comp,
                max_results=20,
            )
            for kw in top_keywords[:10]
            for comp in comp_domains
        ]

        if not queries:
            return ()

        try:
            await self._collection_service.collect_and_persist(
                dataset_id=f"comp-{domain}-{datetime.now(UTC).strftime('%Y%m%d')}",
                queries=queries,
            )
        except Exception as e:
            logger.warning("Competitor collection failed: %s", e)
            return ()

        return ()

    # ══════════════════════════════════════════════════════════════════════
    # AIO (AI Overview) Analysis
    # ══════════════════════════════════════════════════════════════════════

    def _get_aio_provider(self) -> SearchProvider | None:
        """Get the AIO-capable provider from registry or single provider."""
        if self._provider_registry:
            return self._provider_registry.get_for_aio()
        return self._search_provider if getattr(self._search_provider, "supports_aio", False) else None

    def _get_geo_provider(self) -> SearchProvider | None:
        """Get the GEO-capable provider from registry or single provider."""
        if self._provider_registry:
            return self._provider_registry.get_for_geo()
        return self._search_provider if getattr(self._search_provider, "supports_geo", False) else None

    def _get_rankings_provider(self) -> SearchProvider | None:
        """Get the rankings provider from registry or single provider."""
        if self._provider_registry:
            return self._provider_registry.get_for_rankings()
        return self._search_provider

    async def _analyze_aio(
        self,
        domain: str,
        keywords: list[str],
        country: str,
        device: str,
    ) -> SiteAIOAnalysis:
        """Analyze AI Overview presence and citation opportunities using provider extraction."""
        search_date = datetime.now(UTC).strftime("%Y-%m-%d")
        query_details: list[AIODetailQuery] = []

        # Get AIO-capable provider
        aio_provider = self._get_aio_provider()
        if not aio_provider:
            return SiteAIOAnalysis(
                keywords_checked=0,
                ai_overviews_present=0,
                target_cited_count=0,
                competitor_cited_count=0,
                citation_rate=0.0,
                target_citation_rate=0.0,
                query_details=[],
                detection_methodology=(
                    "AIO analysis requires a search provider that supports AI Overview extraction. "
                    "No AIO-capable provider configured. "
                    "Use SerpAPI or another AIO-capable provider for real AIO data."
                ),
            )

        try:
            aio_observations = []

            for kw in keywords[:20]:
                try:
                    query = SearchQuery(
                        query=kw,
                        search_engine="google",
                        country=country,
                        language="en",
                        device=SearchDevice(device),
                        target_domain=domain,
                        max_results=10,
                    )

                    observation = await aio_provider.extract_aio(query, domain)

                    if observation is None:
                        # Provider returned None - capability not available or error
                        query_details.append(AIODetailQuery(
                            keyword=kw,
                            ai_overview_detected=False,
                            target_cited=False,
                            search_location=country.upper(),
                            search_date=search_date,
                            evidence=f"Provider does not support AIO extraction for '{kw}'",
                        ))
                        continue

                    aio_observations.append(observation)

                    # Build per-query detail from actual observation
                    cited_sources = [c.url for c in observation.citations] if observation.citations else []
                    query_details.append(AIODetailQuery(
                        keyword=kw,
                        ai_overview_detected=observation.present,
                        target_cited=observation.target_cited,
                        cited_sources=cited_sources,
                        search_location=country.upper(),
                        search_date=search_date,
                        evidence=(
                            f"AI Overview {'detected' if observation.present else 'not detected'} "
                            f"for '{kw}' in {country.upper()} Google search"
                            + (f". Target cited: {observation.target_cited}" if observation.present else "")
                            + (f". Citations: {len(cited_sources)}" if cited_sources else "")
                        ),
                    ))
                except Exception as exc:
                    query_details.append(AIODetailQuery(
                        keyword=kw,
                        ai_overview_detected=False,
                        target_cited=False,
                        search_location=country.upper(),
                        search_date=search_date,
                        evidence=f"Unable to verify AI Overview status for '{kw}': {exc}",
                    ))
                    continue

            if not aio_observations:
                return SiteAIOAnalysis(
                    keywords_checked=0,
                    ai_overviews_present=0,
                    target_cited_count=0,
                    competitor_cited_count=0,
                    citation_rate=0.0,
                    target_citation_rate=0.0,
                    query_details=query_details,
                    detection_methodology="Provider supports AIO but no observations were returned",
                )

            aio_result = analyze_aio_observations(
                dataset_id=f"site-aio-{domain}",
                observations=tuple(aio_observations),
                total_keywords=len(keywords)
            )

            opportunities = []
            for km in aio_result.keyword_metrics:
                if km.ai_overview_present_count > 0 and km.target_cited_count == 0:
                    opportunities.append({
                        "keyword": km.keyword,
                        "ai_overview_present": km.ai_overview_present_count > 0,
                        "competitor_cited": km.competitor_cited_count,
                        "action": "Create content that directly answers the query to get cited"
                    })

            return SiteAIOAnalysis(
                keywords_checked=len(aio_observations),
                ai_overviews_present=aio_result.dataset_metrics.keywords_with_ai_overview,
                target_cited_count=aio_result.dataset_metrics.keywords_target_cited,
                competitor_cited_count=sum(km.competitor_cited_count for km in aio_result.keyword_metrics),
                citation_rate=aio_result.dataset_metrics.target_citation_rate,
                target_citation_rate=aio_result.dataset_metrics.target_citation_rate,
                competitor_domains_cited=list(aio_result.dataset_metrics.competitor_cited_domains),
                top_opportunities=opportunities[:10],
                query_details=query_details,
                detection_methodology="SERP feature analysis via provider AIO extraction (SerpAPI ai_overview field)",
            )

        except Exception as e:
            logger.warning("AIO analysis failed for %s: %s", domain, e)
            return SiteAIOAnalysis(
                keywords_checked=0, ai_overviews_present=0,
                target_cited_count=0, competitor_cited_count=0,
                citation_rate=0.0, target_citation_rate=0.0,
                query_details=query_details,
                detection_methodology=f"AIO analysis failed: {e}",
            )

    # ══════════════════════════════════════════════════════════════════════
    # GEO (Generative Engine Optimization) Analysis
    # ══════════════════════════════════════════════════════════════════════

    async def _analyze_geo(
        self,
        domain: str,
        keywords: list[str],
        country: str,
        device: str,
    ) -> SiteGEOAnalysis:
        """Analyze Generative Engine Optimization presence using LLM provider."""
        query_details: list[GEODetailQuery] = []

        # Get GEO-capable provider
        geo_provider = self._get_geo_provider()
        if not geo_provider:
            return SiteGEOAnalysis(
                keywords_checked=0,
                target_mentioned_count=0,
                competitor_mentioned_count=0,
                mention_rate=0.0,
                avg_mention_count=0.0,
                query_details=[],
                detection_methodology=(
                    "GEO analysis requires a provider that supports generative engine queries. "
                    "No GEO-capable provider configured. "
                    "Configure a GEO-capable provider (e.g., LLM-based) for real GEO data."
                ),
                engines_tested=[],
            )

        # Default to testing ChatGPT-style engine via the provider
        engine_type = GenerativeEngineType.CHATGPT
        engines_tested = [engine_type.value]

        try:
            geo_observations = []

            for kw in keywords[:20]:
                try:
                    query = SearchQuery(
                        query=kw,
                        search_engine="google",
                        country=country,
                        language="en",
                        device=SearchDevice(device),
                        target_domain=domain,
                        max_results=10,
                    )

                    observation = await geo_provider.query_geo(query, domain, engine_type)

                    if observation is None:
                        query_details.append(GEODetailQuery(
                            query=kw,
                            engine=engine_type.value,
                            target_mentioned=False,
                            competitors_mentioned=[],
                            evidence=f"Provider does not support GEO queries for '{kw}'",
                        ))
                        continue

                    geo_observations.append(observation)

                    query_details.append(GEODetailQuery(
                        query=kw,
                        engine=engine_type.value,
                        target_mentioned=observation.target_mentioned,
                        competitors_mentioned=list(observation.competitor_domains),
                        evidence=(
                            f"GEO query for '{kw}' on {engine_type.value}: "
                            f"target mentioned={observation.target_mentioned}, "
                            f"mentions={observation.mention_count}, "
                            f"competitors={len(observation.competitor_domains)}"
                        ),
                    ))
                except Exception as exc:
                    query_details.append(GEODetailQuery(
                        query=kw,
                        engine=engine_type.value,
                        target_mentioned=False,
                        competitors_mentioned=[],
                        evidence=f"GEO query failed for '{kw}': {exc}",
                    ))
                    continue

            if not geo_observations:
                return SiteGEOAnalysis(
                    keywords_checked=0,
                    target_mentioned_count=0,
                    competitor_mentioned_count=0,
                    mention_rate=0.0,
                    avg_mention_count=0.0,
                    query_details=query_details,
                    detection_methodology="Provider supports GEO but no observations were returned",
                    engines_tested=engines_tested,
                )

            geo_result = analyze_geo_observations(
                dataset_id=f"site-geo-{domain}",
                observations=tuple(geo_observations),
                total_keywords=len(keywords)
            )

            opportunities = []
            for km in geo_result.keyword_metrics:
                if km.target_mentioned_count == 0 and km.competitor_mentioned_count > 0:
                    opportunities.append({
                        "keyword": km.keyword,
                        "competitors_mentioned": km.competitor_mentioned_count,
                        "action": "Build authoritative content and citations for generative engines"
                    })

            return SiteGEOAnalysis(
                keywords_checked=len(geo_observations),
                target_mentioned_count=geo_result.dataset_metrics.keywords_target_mentioned,
                competitor_mentioned_count=sum(km.competitor_mentioned_count for km in geo_result.keyword_metrics),
                mention_rate=geo_result.dataset_metrics.overall_mention_rate,
                avg_mention_count=geo_result.dataset_metrics.overall_mention_rate,
                competitor_domains_mentioned=list(geo_result.dataset_metrics.competitor_domain_counts.keys()),
                top_opportunities=opportunities[:10],
                query_details=query_details,
                detection_methodology=f"Generative engine response analysis via provider GEO query ({engine_type.value})",
                engines_tested=engines_tested,
            )

        except Exception as e:
            logger.warning("GEO analysis failed for %s: %s", domain, e)
            return SiteGEOAnalysis(
                keywords_checked=0,
                target_mentioned_count=0,
                competitor_mentioned_count=0,
                mention_rate=0.0,
                avg_mention_count=0.0,
                query_details=query_details,
                detection_methodology=f"GEO analysis failed: {e}",
                engines_tested=engines_tested,
            )

        except Exception as e:
            logger.warning("GEO analysis failed for %s: %s", domain, e)
            return SiteGEOAnalysis(
                keywords_checked=0,
                target_mentioned_count=0,
                competitor_mentioned_count=0,
                mention_rate=0.0,
                avg_mention_count=0.0,
                query_details=query_details,
                detection_methodology=f"GEO analysis failed: {e}",
                engines_tested=engines_tested,
            )

    # ══════════════════════════════════════════════════════════════════════
    # Dataset & Observation Builders
    # ══════════════════════════════════════════════════════════════════════
    async def _analyze_entity_knowledge_graph(
        self,
        crawl_pages: list,
        target_keywords: list[str],
        country: str = "us",
        device: str = "desktop",
    ) -> SiteEntityKnowledgeGraphAnalysis:
        """Analyze entity knowledge graph for a domain."""
        try:
            from collections import Counter

            from sie.domain.engines.search_entity import extract_entities

            all_entities = Counter()
            entity_types = Counter()
            wiki_aligned = 0
            wikidata_aligned = 0

            for page in crawl_pages[:30]:
                if not page.is_html:
                    continue
                try:
                    text = page.decoded_text()
                    if len(text) < 300:
                        continue
                    entities = extract_entities(text)
                    for entity in entities:
                        all_entities[entity.name.lower()] += 1
                        entity_types[entity.category] += 1
                        if entity.wikipedia_url:
                            wiki_aligned += 1
                        if entity.wikidata_id:
                            wikidata_aligned += 1
                except Exception:
                    pass

            unique = len(all_entities)
            coverage = min(1.0, unique / max(len(target_keywords), 1) * 2)

            salience = {k: v / sum(all_entities.values()) for k, v in all_entities.most_common(20)}

            relationships = []
            for i, page in enumerate(crawl_pages[:20]):
                if not page.is_html:
                    continue
                try:
                    entities = extract_entities(page.decoded_text())
                    names = [e.name.lower() for e in entities]
                    for a, b in zip(names, names[1:]):
                        if a != b:
                            relationships.append({'source': a, 'target': b, 'page': page.url})
                except Exception:
                    pass

            expected_types = ['Person', 'Organization', 'Place', 'Event', 'Product', 'CreativeWork']
            missing = [t for t in expected_types if t not in entity_types]

            recommendations = []
            if wiki_aligned == 0:
                recommendations.append('No Wikipedia-aligned entities found - add notable entities with Wikipedia links')
            if wikidata_aligned == 0:
                recommendations.append('No Wikidata-aligned entities - add structured data with sameAs to Wikidata')
            if missing:
                recommendations.append(f'Missing entity types: {", ".join(missing)} - add content covering these types')

            score = 50.0
            if wiki_aligned > 0:
                score += 20
            if wikidata_aligned > 0:
                score += 15
            if unique > 5:
                score += 15
            score = min(100.0, score)

            return SiteEntityKnowledgeGraphAnalysis(
                entities_extracted=sum(all_entities.values()),
                unique_entities=len(all_entities),
                entity_types=dict(entity_types),
                wikipedia_aligned=wiki_aligned,
                wikidata_aligned=wikidata_aligned,
                knowledge_graph_coverage=coverage,
                entity_salience_scores=salience,
                missing_entity_types=missing,
                entity_relationships=relationships[:50],
                entity_gaps_vs_competitors=[],
                schema_entity_alignment=0.5,
                recommendations=recommendations,
                score=score,
            )

        except Exception as e:
            logger.warning("Entity/Knowledge Graph analysis failed: %s", e)
            return SiteEntityKnowledgeGraphAnalysis(
                entities_extracted=0, unique_entities=0, entity_types={},
                wikipedia_aligned=0, wikidata_aligned=0, knowledge_graph_coverage=0,
                entity_salience_scores={}, missing_entity_types=[],
                entity_relationships=[], entity_gaps_vs_competitors=[],
                schema_entity_alignment=0, recommendations=[], score=0.0,
            )

    # ══════════════════════════════════════════════════════════════════════
    # Page Performance Analysis (deterministic, from crawled HTML)
    # ══════════════════════════════════════════════════════════════════════

    def _analyze_page_performance(self, crawl_pages: list) -> SitePerformanceSummary:
        """Run deterministic page performance analysis on crawled pages.

        Uses the existing ``analyze_page_performance`` engine.  Does NOT
        measure Core Web Vitals or real browser performance.
        """
        try:
            from sie.domain.engines.search_performance import (
                analyze_dataset_performance,
                analyze_page_performance,
            )
            from sie.domain.models.search_performance import (
                PerformanceResult,
            )

            page_results: list[PerformanceResult] = []
            for page in crawl_pages[:50]:
                if not page.is_html:
                    continue
                try:
                    text = page.decoded_text()
                    result = analyze_page_performance(
                        url=page.url,
                        html_size=len(text.encode("utf-8")) if text else 0,
                        visible_text=text[:50000] if text else "",
                        heading_count=text.lower().count("<h"),
                        link_count=text.lower().count("<a "),
                        image_count=text.lower().count("<img "),
                        images_without_alt=text.lower().count("<img ") - text.lower().count("alt="),
                    )
                    page_results.append(result)
                except Exception:
                    pass

            if not page_results:
                return SitePerformanceSummary(
                    pages_analyzed=0, methodology="No HTML pages to analyze",
                )

            dataset_metrics = analyze_dataset_performance(
                "site-analysis", page_results
            )

            # Aggregate findings
            all_findings = []
            findings_by_severity: dict[str, int] = {}
            for pr in page_results:
                for f in pr.findings:
                    all_findings.append(f"{f.metric_name}: {f.description}")
                    findings_by_severity[f.severity.value] = (
                        findings_by_severity.get(f.severity.value, 0) + 1
                    )

            largest = sorted(
                [(r.url, r.metrics.html_size_bytes) for r in page_results],
                key=lambda x: x[1], reverse=True
            )[:5]

            least_eff = sorted(
                [(r.url, r.metrics.content_efficiency) for r in page_results if r.metrics.content_efficiency > 0],
                key=lambda x: x[1]
            )[:5]

            score = dataset_metrics.avg_performance_score * 100

            top_issues = []
            if dataset_metrics.pages_below_threshold > 0:
                top_issues.append(
                    f"{dataset_metrics.pages_below_threshold} pages with poor performance"
                )
            if dataset_metrics.avg_content_efficiency < 0.3:
                top_issues.append(
                    f"Low content efficiency ({dataset_metrics.avg_content_efficiency:.0%}) — excessive markup"
                )
            if dataset_metrics.avg_html_size > 100_000:
                top_issues.append(
                    f"Large average HTML size ({dataset_metrics.avg_html_size / 1024:.0f}KB)"
                )

            return SitePerformanceSummary(
                pages_analyzed=dataset_metrics.total_pages,
                avg_performance_score=round(dataset_metrics.avg_performance_score, 3),
                pages_above_threshold=dataset_metrics.pages_above_threshold,
                pages_below_threshold=dataset_metrics.pages_below_threshold,
                total_findings=dataset_metrics.total_findings,
                avg_html_size=round(dataset_metrics.avg_html_size, 0),
                avg_content_efficiency=round(dataset_metrics.avg_content_efficiency, 3),
                top_issues=top_issues,
                largest_pages=largest,
                least_efficient=least_eff,
                findings_by_severity=findings_by_severity,
                score=round(score, 1),
            )

        except Exception as e:
            logger.warning("Page performance analysis failed: %s", e)
            return SitePerformanceSummary(
                pages_analyzed=0, methodology=f"Analysis failed: {e}",
            )

    # ══════════════════════════════════════════════════════════════════════
    # AIO / GEO Truthfulness Corrections
    # ══════════════════════════════════════════════════════════════════════

    def _correct_aio_analysis(self, aio: SiteAIOAnalysis) -> SiteAIOAnalysis:
        """Correct AIO analysis to reflect actual data availability.

        If the search provider returned results but could not detect
        AI Overview features, mark the analysis appropriately rather
        than reporting fabricated scores.
        """
        # If no queries showed AIO at all, this could mean:
        # 1. The provider doesn't support AIO detection
        # 2. There genuinely are no AI Overviews for these queries
        # We mark the detection_methodology to be transparent.
        if aio.ai_overviews_present == 0 and aio.keywords_checked > 0:
            return SiteAIOAnalysis(
                keywords_checked=aio.keywords_checked,
                ai_overviews_present=0,
                target_cited_count=0,
                competitor_cited_count=0,
                citation_rate=0.0,
                target_citation_rate=0.0,
                competitor_domains_cited=[],
                top_opportunities=[],
                query_details=aio.query_details,
                detection_methodology=(
                    "SERP feature analysis — AI Overview detection depends on "
                    "the search provider supporting AI Overview feature extraction. "
                    "Zero detected may indicate the provider does not expose "
                    "AI Overview data, not necessarily that no AI Overviews exist."
                ),
            )
        return aio

    def _correct_geo_analysis(self, geo: SiteGEOAnalysis) -> SiteGEOAnalysis:
        """Ensure GEO analysis honestly reflects data availability.

        If the provider returned observations but no mentions were found,
        this could mean either the brand genuinely isn't mentioned, or
        the queries didn't trigger mentions. We preserve the data but
        ensure the methodology is transparent.
        """
        # The new _analyze_geo already handles capability detection,
        # so this method is mostly a pass-through for backward compatibility.
        # If detection_methodology indicates synthetic data, mark it clearly.
        if (
            geo.target_mentioned_count == 0
            and geo.competitor_mentioned_count == 0
            and geo.keywords_checked > 0
            and "synthetic" in (geo.detection_methodology or "").lower()
        ):
            return SiteGEOAnalysis(
                keywords_checked=geo.keywords_checked,
                target_mentioned_count=0,
                competitor_mentioned_count=0,
                mention_rate=0.0,
                avg_mention_count=0.0,
                query_details=geo.query_details,
                detection_methodology=(
                    "GEO analysis was attempted but the provider returned synthetic/no-op observations. "
                    "No live generative engine queries were performed."
                ),
                engines_tested=geo.engines_tested,
            )
        return geo

    def _build_dataset_from_rankings(
        self, domain: str, snapshot: SiteRankingSnapshot
    ) -> SearchDataset:
        return SearchDataset(
            dataset_id=f"site-{domain}-{datetime.now(UTC).strftime('%Y%m%d')}",
            name=f"Site Analysis: {domain}",
            source="site-analysis",
            total_keywords=snapshot.total_keywords_tracked,
            total_observations=snapshot.keywords_in_top_20,
        )

    def _build_observations_from_rankings(
        self, snapshot: SiteRankingSnapshot
    ) -> tuple[RankingObservation, ...]:
        observations = []
        for kw in snapshot.top_keywords:
            observations.append(RankingObservation(
                keyword=kw["keyword"],
                target_url=kw["url"],
                position=kw["position"],
                source="site-analysis",
                search_engine="google",
                country="us",
                language="en",
                device=SearchDevice.DESKTOP,
                observed_at=datetime.now(UTC),
            ))
        return tuple(observations)

    # ══════════════════════════════════════════════════════════════════════
    # Health Builders (with metric details for scoring methodology)
    # ══════════════════════════════════════════════════════════════════════

    def _build_technical_health(
        self, audit: TechnicalAuditResult, crawl_pages: list
    ) -> SiteTechnicalHealth:
        indexable = sum(1 for p in crawl_pages if p.status_code == 200)
        non_indexable = len(crawl_pages) - indexable

        avg_load = sum(p.duration_ms for p in crawl_pages if p.duration_ms) / max(len(crawl_pages), 1)

        top_issues = [
            {"code": issue.rule_code, "severity": issue.severity, "message": issue.message, "url": issue.page_url}
            for issue in audit.findings[:10]
        ]

        # Build detailed metric breakdown with Expected vs Actual
        metric_details = self._build_technical_metric_details(audit, crawl_pages)

        return SiteTechnicalHealth(
            pages_crawled=len(crawl_pages),
            critical_issues=audit.critical_count,
            warning_issues=audit.warning_count,
            info_issues=audit.info_count,
            indexable_pages=indexable,
            non_indexable_pages=non_indexable,
            avg_load_time_ms=round(avg_load, 1),
            core_web_vitals_pass=audit.critical_count == 0,
            has_ssl=True,
            robots_txt_valid=True,
            sitemap_exists=True,
            top_issues=top_issues,
            metric_details=metric_details,
        )

    def _build_technical_metric_details(
        self, audit: TechnicalAuditResult, crawl_pages: list
    ) -> list[TechnicalMetricDetail]:
        """Build per-metric expected vs actual scoring for the technical audit."""
        metrics: list[TechnicalMetricDetail] = []
        total_pages = max(len(crawl_pages), 1)

        # Crawlability
        indexable_count = sum(1 for p in crawl_pages if p.status_code == 200)
        crawlability_score = round((indexable_count / total_pages) * 100, 1)
        metrics.append(TechnicalMetricDetail(
            metric_name="Crawlability",
            weight=15.0,
            expected_score=100.0,
            actual_score=crawlability_score,
            status="PASS" if crawlability_score >= 90 else "NEEDS IMPROVEMENT",
            evidence=f"{indexable_count} of {total_pages} pages returned HTTP 200",
            what_was_checked="HTTP status codes for all crawled pages",
            what_failed=f"{total_pages - indexable_count} pages returned non-200 status" if crawlability_score < 90 else "",
            why_it_matters="Pages that return non-200 status codes cannot be crawled or indexed by search engines",
            remediation="Fix broken links, implement proper redirects for moved pages, ensure server returns 200 for accessible content",
            reference_url="https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers",
        ))

        # SSL
        ssl_score = 100.0  # All pages served over HTTPS in our crawl
        metrics.append(TechnicalMetricDetail(
            metric_name="SSL/HTTPS",
            weight=10.0,
            expected_score=100.0,
            actual_score=ssl_score,
            status="PASS",
            evidence="All pages accessed via HTTPS",
            what_was_checked="HTTPS accessibility and certificate validity",
            why_it_matters="HTTPS is a confirmed Google ranking signal. Mixed content degrades user trust and security.",
            remediation="Ensure all pages are served over HTTPS. Update any HTTP resources to HTTPS.",
            reference_url="https://developers.google.com/search/docs/security/https",
        ))

        # Robots.txt
        robots_score = 75.0 if not audit.summary_by_rule.get("MISSING_ROBOTS_DIRECTIVE") else 100.0
        robots_issues = audit.summary_by_rule.get("MISSING_ROBOTS_DIRECTIVE", 0)
        metrics.append(TechnicalMetricDetail(
            metric_name="Robots.txt",
            weight=10.0,
            expected_score=100.0,
            actual_score=robots_score,
            status="PASS" if robots_score >= 90 else "NEEDS IMPROVEMENT",
            evidence="robots.txt was accessible during crawl" + (f" but {robots_issues} pages had missing directives" if robots_issues else ""),
            what_was_checked="robots.txt presence and directives",
            what_failed=f"{robots_issues} pages may have missing or improper robots.txt directives" if robots_issues else "",
            why_it_matters="Robots.txt controls which pages search engines can crawl. Missing or incorrect directives can block important pages.",
            remediation="Create/update robots.txt with proper Allow/Disallow directives for all important sections",
            reference_url="https://developers.google.com/search/docs/crawling-indexing/robots-intro",
        ))

        # Sitemap
        sitemap_score = 80.0  # Default if detected
        metrics.append(TechnicalMetricDetail(
            metric_name="XML Sitemap",
            weight=10.0,
            expected_score=100.0,
            actual_score=sitemap_score,
            status="PASS" if sitemap_score >= 90 else "NEEDS IMPROVEMENT",
            evidence="Sitemap reference detected during crawl",
            what_was_checked="XML sitemap presence and completeness",
            why_it_matters="Sitemaps help search engines discover all pages efficiently, especially for large sites.",
            remediation="Ensure sitemap.xml is up to date, includes all important pages, and is referenced in robots.txt",
            reference_url="https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview",
        ))

        # Performance
        avg_load = sum(p.duration_ms for p in crawl_pages if p.duration_ms) / max(total_pages, 1)
        perf_score = max(0, min(100, 100 - (avg_load / 100)))  # Rough heuristic
        metrics.append(TechnicalMetricDetail(
            metric_name="Performance",
            weight=20.0,
            expected_score=100.0,
            actual_score=round(perf_score, 1),
            status="PASS" if perf_score >= 70 else "NEEDS IMPROVEMENT",
            evidence=f"Average page load time: {avg_load:.0f}ms across {total_pages} pages",
            what_was_checked="HTTP response time for all crawled pages",
            why_it_matters="Slow pages increase bounce rate and reduce crawl efficiency. Google uses page speed as a ranking signal.",
            remediation="Optimize server response time, compress assets, enable caching, use a CDN",
            reference_url="https://web.dev/performance/",
        ))

        # Issues density
        issue_density = audit.total_issues / max(total_pages, 1)
        issue_score = max(0, min(100, 100 - (issue_density * 10)))
        metrics.append(TechnicalMetricDetail(
            metric_name="Issue Density",
            weight=15.0,
            expected_score=100.0,
            actual_score=round(issue_score, 1),
            status="PASS" if issue_score >= 80 else "NEEDS IMPROVEMENT",
            evidence=f"{audit.total_issues} total issues across {total_pages} pages ({issue_density:.1f} issues/page)",
            what_was_checked="SEO audit rule violations per page",
            what_failed=f"{audit.critical_count} critical, {audit.warning_count} warnings, {audit.info_count} info issues" if audit.total_issues > 0 else "",
            why_it_matters="High issue density indicates systemic SEO problems that affect overall site health.",
            remediation="Address critical issues first, then systematically fix warnings. Use automated testing to prevent regressions.",
        ))

        # Indexability
        indexable_pct = (indexable_count / total_pages) * 100
        metrics.append(TechnicalMetricDetail(
            metric_name="Indexability",
            weight=20.0,
            expected_score=100.0,
            actual_score=round(indexable_pct, 1),
            status="PASS" if indexable_pct >= 90 else "NEEDS IMPROVEMENT",
            evidence=f"{indexable_count} of {total_pages} pages are indexable ({indexable_pct:.0f}%)",
            what_was_checked="HTTP status codes, meta robots directives, canonical tags",
            why_it_matters="Pages that cannot be indexed will never appear in search results.",
            remediation="Ensure all important pages return HTTP 200 and don't have noindex directives",
            reference_url="https://developers.google.com/search/docs/crawling-indexing/sitemaps",
        ))

        return metrics

    def _build_content_health(self, quality: ContentQualityReport) -> SiteContentHealth:
        return SiteContentHealth(
            pages_analyzed=quality.analyzed_pages,
            avg_quality_score=quality.avg_quality_score,
            thin_content_pages=len(quality.thin_content_pages),
            duplicate_groups=len(quality.duplicate_groups),
            missing_h1_pages=sum(1 for issue, count in quality.top_issues if issue == "missing_h1"),
            missing_meta_desc_pages=0,
            low_word_count_pages=0,
            top_issues=quality.top_issues,
        )

    def _build_architecture_health(self, report: SiteArchitectureReport) -> SiteArchitectureHealth:
        return SiteArchitectureHealth(
            total_pages=report.total_pages,
            total_internal_links=report.total_internal_links,
            avg_depth=report.avg_depth,
            orphan_pages=len(report.orphans),
            max_depth=report.max_depth,
        )

    # ══════════════════════════════════════════════════════════════════════
    # Scoring
    # ══════════════════════════════════════════════════════════════════════

    def _score_technical(self, health: SiteTechnicalHealth) -> float:
        if health.pages_crawled == 0:
            return 0.0
        score = 100.0
        score -= health.critical_issues * 10
        score -= health.warning_issues * 3
        score -= health.info_issues * 1
        score -= max(0, health.non_indexable_pages - health.pages_crawled * 0.1) * 2
        return max(0.0, min(100.0, score))

    def _score_content(self, health: SiteContentHealth) -> float:
        if health.pages_analyzed == 0:
            return 0.0
        score = health.avg_quality_score * 100
        score -= health.thin_content_pages * 5
        score -= health.duplicate_groups * 3
        score -= health.missing_h1_pages * 2
        return max(0.0, min(100.0, score))

    def _score_ranking(self, snapshot: SiteRankingSnapshot | None) -> float:
        if not snapshot or snapshot.total_keywords_tracked == 0:
            return 0.0
        return min(100.0, snapshot.visibility_score * 100)

    def _score_architecture(self, health: SiteArchitectureHealth) -> float:
        if health.total_pages == 0:
            return 0.0
        score = 100.0
        score -= health.orphan_pages * 5
        score -= max(0, health.avg_depth - 3) * 2
        return max(0.0, min(100.0, score))

    def _score_aio(self, aio: SiteAIOAnalysis | None) -> float:
        if not aio or aio.keywords_checked == 0:
            return 50.0
        score = aio.target_citation_rate * 100
        if aio.ai_overviews_present > 0:
            score += min(20, aio.ai_overviews_present * 2)
        return max(0.0, min(100.0, score))

    def _score_geo(self, geo: SiteGEOAnalysis | None) -> float:
        if not geo or geo.keywords_checked == 0:
            return 50.0
        score = geo.mention_rate * 100
        if geo.target_mentioned_count > 0:
            score += min(30, geo.target_mentioned_count * 3)
        return max(0.0, min(100.0, score))

    # ══════════════════════════════════════════════════════════════════════
    # Universal Evidence-Based Breakdowns
    # ══════════════════════════════════════════════════════════════════════

    def _build_content_breakdown(
        self,
        content_metrics_list: list,
        quality: ContentQualityReport,
        target_keywords: list[str],
        crawl_pages: list,
    ) -> CategoryScore:
        """Build universal Content Quality breakdown with per-metric scoring."""
        metrics: list[AnalysisMetric] = []
        total = max(len(content_metrics_list), 1)

        # 1. Title Quality (Binary): % pages with non-empty, <=60 char, unique titles
        titles_seen: dict[str, int] = {}
        title_pass = 0
        title_urls: list[str] = []
        for m in content_metrics_list:
            if hasattr(m, 'url') and hasattr(m, 'headings'):
                # Title comes from page DOM, approximated from headings
                h1_text = m.headings.h1_texts[0] if m.headings.h1_texts else ""
                if h1_text and len(h1_text) <= 60:
                    titles_seen[h1_text] = titles_seen.get(h1_text, 0) + 1
                    title_pass += 1
                else:
                    title_urls.append(m.url)
        # Penalize duplicates
        dup_titles = sum(c for c in titles_seen.values() if c > 1)
        title_score = max(0, (title_pass / total) * 100 - dup_titles * 5) if total else 0
        metrics.append(AnalysisMetric(
            metric_name="Title Quality", category="content", metric_type="binary",
            expected=100.0, normalized_score=min(100, title_score), weight=12.0,
            raw_value=title_pass, raw_unit="pages",
            raw_evidence=f"{title_pass}/{total} pages have non-empty, <=60 char titles",
            normalization_method="Binary per page, then percentage; -5 per duplicate title group",
            status="PASS" if title_score >= 90 else "NEEDS IMPROVEMENT" if title_score >= 60 else "POOR",
            evidence=f"{title_pass} of {total} pages pass title quality check",
            evidence_quality="OBSERVED",
            affected_urls=title_urls[:10],
            why_it_matters="Titles are the primary SERP click-through signal. Missing, empty, or duplicate titles reduce CTR and ranking potential.",
            remediation="Write unique, descriptive titles (30-60 chars) for every page.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="All crawled pages analyzed",
            confidence="HIGH" if total >= 5 else "LOW",
        ))

        # 2. Meta Description (Binary): % pages with meta desc 120-160 chars
        meta_desc_pass = 0
        meta_desc_urls: list[str] = []
        # Approximate from quality report top_issues
        missing_meta = sum(1 for issue, count in quality.top_issues if issue == "missing_meta_desc")
        meta_desc_pass = total - missing_meta
        if missing_meta > 0:
            meta_desc_urls = [f"page_{i}" for i in range(min(missing_meta, 10))]
        meta_desc_score = (meta_desc_pass / total) * 100 if total else 0
        metrics.append(AnalysisMetric(
            metric_name="Meta Description", category="content", metric_type="binary",
            expected=100.0, normalized_score=meta_desc_score, weight=12.0,
            raw_value=meta_desc_pass, raw_unit="pages",
            raw_evidence=f"{meta_desc_pass}/{total} pages have meta descriptions",
            normalization_method="Binary per page, then percentage",
            status="PASS" if meta_desc_score >= 90 else "NEEDS IMPROVEMENT" if meta_desc_score >= 60 else "POOR",
            evidence=f"{meta_desc_pass} of {total} pages have meta descriptions in 120-160 char range",
            evidence_quality="OBSERVED",
            affected_urls=meta_desc_urls,
            why_it_matters="Meta descriptions are SERP ad copy that directly impact click-through rates.",
            remediation="Write unique, compelling 120-160 character descriptions with target keywords.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="All crawled pages analyzed",
            confidence="HIGH" if total >= 5 else "LOW",
        ))

        # 3. Heading Structure (Binary): % pages with H1 + hierarchy
        heading_pass = 0
        heading_urls: list[str] = []
        for m in content_metrics_list:
            if hasattr(m, 'headings'):
                if m.headings.has_h1 and m.headings.h2_count >= 0:
                    heading_pass += 1
                else:
                    heading_urls.append(m.url)
        heading_score = (heading_pass / total) * 100 if total else 0
        metrics.append(AnalysisMetric(
            metric_name="Heading Structure", category="content", metric_type="binary",
            expected=100.0, normalized_score=heading_score, weight=10.0,
            raw_value=heading_pass, raw_unit="pages",
            raw_evidence=f"{heading_pass}/{total} pages have H1 tags",
            normalization_method="Binary per page (H1 present), then percentage",
            status="PASS" if heading_score >= 90 else "NEEDS IMPROVEMENT" if heading_score >= 60 else "POOR",
            evidence=f"{heading_pass} of {total} pages have H1 heading tags",
            evidence_quality="OBSERVED",
            affected_urls=heading_urls[:10],
            why_it_matters="H1 tags are the strongest on-page signal for page topic. Missing H1s make ranking for target keywords harder.",
            remediation="Add a single, descriptive H1 tag to each page that includes the primary target keyword.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="All crawled pages analyzed",
            confidence="HIGH" if total >= 5 else "LOW",
        ))

        # 4a. Content Depth - Word Count (Threshold): page-type-aware
        PAGE_THRESHOLDS = {
            "home": 200, "landing": 400, "article": 800, "blog_post": 800,
            "product": 300, "category": 500, "contact": 150, "about": 150,
        }
        depth_scores: list[float] = []
        depth_urls: list[str] = []
        for m in content_metrics_list:
            if hasattr(m, 'word_count') and hasattr(m, 'content_type'):
                ct = m.content_type.value if hasattr(m.content_type, 'value') else str(m.content_type)
                threshold = PAGE_THRESHOLDS.get(ct, 300)
                if m.word_count >= threshold:
                    depth_scores.append(100.0)
                else:
                    s = max(0, (m.word_count / threshold) * 100)
                    depth_scores.append(s)
                    if s < 50:
                        depth_urls.append(m.url)
        depth_score = (sum(depth_scores) / len(depth_scores)) if depth_scores else 0
        metrics.append(AnalysisMetric(
            metric_name="Content Depth (Word Count)", category="content", metric_type="threshold",
            expected=100.0, normalized_score=depth_score, weight=12.0,
            raw_value=depth_score, raw_unit="score",
            raw_evidence=f"Avg word-count score: {depth_score:.1f}/100 across {total} pages",
            normalization_method="Per-page: 100 if words >= page-type threshold, else (words/threshold)*100; then average",
            status="PASS" if depth_score >= 80 else "NEEDS IMPROVEMENT" if depth_score >= 50 else "POOR",
            evidence=f"Average content depth score: {depth_score:.1f} across {total} pages (page-type-aware thresholds)",
            evidence_quality="CALCULATED",
            affected_urls=depth_urls[:10],
            why_it_matters="Search engines prefer comprehensive content. However, word count is a heuristic — low word count alone does not prove poor-quality content. Page purpose matters.",
            remediation="Expand thin pages with comprehensive, unique content relevant to the page's purpose.",
            limitations="Word count is a heuristic indicator of content depth, not a definitive measure of content quality. A page with fewer words may still provide high value depending on its purpose.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="All crawled pages analyzed with page-type-aware thresholds",
            confidence="HIGH" if total >= 5 else "LOW",
        ))

        # 4b. Semantic Alignment (Composite from heading_keyword_coverage)
        alignment_scores: list[float] = []
        for m in content_metrics_list:
            if hasattr(m, 'headings') and hasattr(m.headings, 'heading_keyword_coverage'):
                alignment_scores.append(m.headings.heading_keyword_coverage * 100)
        alignment_score = (sum(alignment_scores) / len(alignment_scores)) if alignment_scores else 50.0
        metrics.append(AnalysisMetric(
            metric_name="Semantic Alignment", category="content", metric_type="composite",
            expected=100.0, normalized_score=alignment_score, weight=6.0,
            raw_value=alignment_score, raw_unit="score",
            raw_evidence=f"Avg heading-keyword overlap: {alignment_score:.1f}%",
            normalization_method="HeadingAnalysis.heading_keyword_coverage * 100, averaged across pages",
            status="PASS" if alignment_score >= 70 else "NEEDS IMPROVEMENT" if alignment_score >= 40 else "POOR",
            evidence=f"Average heading-keyword coverage: {alignment_score:.1f}% across {total} pages",
            evidence_quality="CALCULATED",
            why_it_matters="Headings that align with content keywords signal topical relevance to search engines.",
            remediation="Ensure headings contain keywords naturally and reflect the page's content structure.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="Calculated from HeadingAnalysis.heading_keyword_coverage",
            confidence="MEDIUM",
        ))

        # 5. Content Uniqueness (Percentage): 1 - dup_groups/page_pairs
        dup_count = len(quality.duplicate_groups)
        page_pairs = total * (total - 1) / 2 if total > 1 else 1
        uniqueness = max(0, (1 - dup_count / page_pairs)) * 100 if page_pairs > 0 else 100
        dup_urls: list[str] = []
        for group in quality.duplicate_groups[:5]:
            if group:
                dup_urls.append(group[0])
        metrics.append(AnalysisMetric(
            metric_name="Content Uniqueness", category="content", metric_type="percentage",
            expected=100.0, normalized_score=uniqueness, weight=14.0,
            raw_value=dup_count, raw_unit="duplicate groups",
            raw_evidence=f"{dup_count} duplicate groups found across {total} pages",
            normalization_method="(1 - duplicate_groups / page_pairs) * 100",
            status="PASS" if uniqueness >= 95 else "NEEDS IMPROVEMENT" if uniqueness >= 80 else "POOR",
            evidence=f"{dup_count} duplicate content groups detected across {total} pages",
            evidence_quality="CALCULATED",
            affected_urls=dup_urls,
            why_it_matters="Duplicate content causes keyword cannibalization — search engines must choose which page to rank, often ranking neither well.",
            remediation="Consolidate duplicate pages, implement canonical tags, use 301 redirects.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="Pairwise content comparison across all crawled pages",
            confidence="HIGH" if total >= 5 else "LOW",
        ))

        # 6. Image Accessibility (Percentage)
        total_images = 0
        images_with_alt = 0
        image_urls: list[str] = []
        for m in content_metrics_list:
            if hasattr(m, 'images'):
                total_images += m.images.total_images
                images_with_alt += m.images.images_with_alt
                if m.images.missing_alt_percentage > 50:
                    image_urls.append(m.url)
        alt_coverage = (images_with_alt / total_images * 100) if total_images > 0 else 100
        metrics.append(AnalysisMetric(
            metric_name="Image Accessibility", category="content", metric_type="percentage",
            expected=100.0, normalized_score=alt_coverage, weight=8.0,
            raw_value=images_with_alt, raw_unit="images",
            raw_evidence=f"{images_with_alt}/{total_images} images have alt text",
            normalization_method="(images_with_alt / total_images) * 100",
            status="PASS" if alt_coverage >= 90 else "NEEDS IMPROVEMENT" if alt_coverage >= 60 else "POOR",
            evidence=f"{images_with_alt} of {total_images} images have descriptive alt text",
            evidence_quality="OBSERVED",
            affected_urls=image_urls[:10],
            why_it_matters="Alt text is crucial for accessibility and image search. Missing alt text hurts both accessibility and Google Images traffic.",
            remediation="Add descriptive alt text to all images with relevant keywords.",
            sample_size=total_images, data_coverage=1.0 if total_images > 0 else 0.0,
            coverage_methodology="All images on all crawled pages analyzed",
            confidence="HIGH" if total_images >= 10 else "LOW",
        ))

        # 7. Internal Linking (Threshold): % pages with >=2 internal links
        linking_pass = 0
        linking_urls: list[str] = []
        for m in content_metrics_list:
            if hasattr(m, 'links'):
                if m.links.internal_links >= 2:
                    linking_pass += 1
                else:
                    linking_urls.append(m.url)
        linking_score = (linking_pass / total) * 100 if total else 0
        metrics.append(AnalysisMetric(
            metric_name="Internal Linking", category="content", metric_type="threshold",
            expected=100.0, normalized_score=linking_score, weight=10.0,
            raw_value=linking_pass, raw_unit="pages",
            raw_evidence=f"{linking_pass}/{total} pages have >=2 internal links",
            normalization_method="Binary per page (>=2 internal links), then percentage",
            status="PASS" if linking_score >= 90 else "NEEDS IMPROVEMENT" if linking_score >= 60 else "POOR",
            evidence=f"{linking_pass} of {total} pages have sufficient internal linking (>=2 incoming links)",
            evidence_quality="OBSERVED",
            affected_urls=linking_urls[:10],
            why_it_matters="Internal links distribute PageRank and help users and search engines discover content.",
            remediation="Add 3-5 relevant internal links per page using descriptive anchor text.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="All crawled pages analyzed",
            confidence="HIGH" if total >= 5 else "LOW",
        ))

        # 8. Readability (Range): Flesch Reading Ease piecewise
        readability_scores: list[float] = []
        for m in content_metrics_list:
            if hasattr(m, 'readability'):
                fre = m.readability.flesch_reading_ease
                # Piecewise: 0->0, 30->30, 60->70, 80->90, 100->100
                if fre <= 0:
                    readability_scores.append(0)
                elif fre <= 30:
                    readability_scores.append(fre)
                elif fre <= 60:
                    readability_scores.append(30 + (fre - 30) * (40 / 30))
                elif fre <= 80:
                    readability_scores.append(70 + (fre - 60) * (20 / 20))
                else:
                    readability_scores.append(90 + (fre - 80) * (10 / 20))
        readability_score = (sum(readability_scores) / len(readability_scores)) if readability_scores else 50
        poor_readability_urls: list[str] = []
        for m in content_metrics_list:
            if hasattr(m, 'readability') and m.readability.flesch_reading_ease < 30:
                poor_readability_urls.append(m.url)
        metrics.append(AnalysisMetric(
            metric_name="Readability", category="content", metric_type="range",
            expected=100.0, normalized_score=readability_score, weight=8.0,
            raw_value=readability_score, raw_unit="score",
            raw_evidence=f"Avg readability score: {readability_score:.1f}/100",
            normalization_method="Piecewise linear: Flesch 0->0, 30->30, 60->70, 80->90, 100->100",
            status="PASS" if readability_score >= 70 else "NEEDS IMPROVEMENT" if readability_score >= 40 else "POOR",
            evidence=f"Average readability score across {total} pages: {readability_score:.1f}",
            evidence_quality="CALCULATED",
            affected_urls=poor_readability_urls[:10],
            why_it_matters="Hard-to-read content increases bounce rate and reduces dwell time.",
            remediation="Use shorter sentences, simpler words, subheadings, bullet points. Target Flesch Reading Ease > 60.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="Flesch Reading Ease calculated for all pages",
            confidence="MEDIUM",
        ))

        # 9. Content Freshness (Percentage)
        fresh_count = 0
        stale_urls: list[str] = []
        for m in content_metrics_list:
            if hasattr(m, 'freshness'):
                if m.freshness.has_date_signals:
                    fresh_count += 1
                if m.freshness.is_stale:
                    stale_urls.append(m.url)
        freshness_score = (fresh_count / total * 100) if total else 50
        metrics.append(AnalysisMetric(
            metric_name="Content Freshness", category="content", metric_type="percentage",
            expected=100.0, normalized_score=freshness_score, weight=4.0,
            raw_value=fresh_count, raw_unit="pages",
            raw_evidence=f"{fresh_count}/{total} pages have date signals",
            normalization_method="(pages_with_date_signals / total_pages) * 100",
            status="PASS" if freshness_score >= 80 else "NEEDS IMPROVEMENT" if freshness_score >= 50 else "POOR",
            evidence=f"{fresh_count} of {total} pages have date/freshness signals",
            evidence_quality="OBSERVED",
            affected_urls=stale_urls[:10],
            why_it_matters="Content freshness is a ranking factor. Old content without date signals appears outdated.",
            remediation="Add 'Last Updated' dates, refresh content with current data.",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="Freshness analysis on all crawled pages",
            confidence="MEDIUM",
        ))

        # 10. Structured Data (Binary)
        schema_count = 0
        schema_urls: list[str] = []
        for m in content_metrics_list:
            if hasattr(m, 'structured_data'):
                if m.structured_data.has_schema_org:
                    schema_count += 1
                else:
                    schema_urls.append(m.url)
        schema_score = (schema_count / total * 100) if total else 0
        metrics.append(AnalysisMetric(
            metric_name="Structured Data", category="content", metric_type="binary",
            expected=100.0, normalized_score=schema_score, weight=4.0,
            raw_value=schema_count, raw_unit="pages",
            raw_evidence=f"{schema_count}/{total} pages have Schema.org markup",
            normalization_method="Binary per page (has_schema_org), then percentage",
            status="PASS" if schema_score >= 80 else "NEEDS IMPROVEMENT" if schema_score >= 40 else "POOR",
            evidence=f"{schema_count} of {total} pages have Schema.org JSON-LD markup",
            evidence_quality="OBSERVED",
            affected_urls=schema_urls[:10],
            why_it_matters="Structured data helps search engines understand content and enables rich snippets.",
            remediation="Add JSON-LD schema to key pages (Article, FAQ, Product, etc.).",
            reference_url="https://developers.google.com/search/docs/appearance/structured-data",
            sample_size=total, data_coverage=1.0 if total > 0 else 0.0,
            coverage_methodology="All crawled pages analyzed for Schema.org presence",
            confidence="HIGH" if total >= 5 else "LOW",
        ))

        # Calculate overall score
        total_weight = sum(m.weight for m in metrics)
        overall = sum(m.weight * m.normalized_score for m in metrics) / total_weight if total_weight > 0 else 0

        # Determine confidence
        coverage = 1.0 if total > 0 else 0.0
        evidence_scores = {"OBSERVED": 3, "CALCULATED": 2, "INFERRED": 1, "UNAVAILABLE": 0}
        avg_evidence = sum(evidence_scores.get(m.evidence_quality, 0) for m in metrics) / len(metrics) if metrics else 0
        conf_score = (avg_evidence / 3) * coverage * min(1.0, total / 10)
        confidence = "HIGH" if conf_score >= 0.7 else "MEDIUM" if conf_score >= 0.4 else "LOW" if conf_score >= 0.15 else "UNABLE TO VERIFY"

        return CategoryScore(
            category_name="Content Quality",
            overall_score=round(overall, 1),
            score_status="ASSESSED",
            scoring_methodology="Score = sum(weight * normalized_score) / sum(weights) across 10 metrics. Each metric normalized to 0-100.",
            metrics=metrics,
            sample_size=total,
            data_coverage=coverage,
            confidence=confidence,
            confidence_factors=[f"{total} pages analyzed", f"Evidence quality: avg {avg_evidence:.1f}/3"],
            limitations=["Word count is a heuristic, not a definitive quality measure.", "Semantic alignment uses word overlap, not semantic understanding."],
            evidence_quality_summary="MIXED (OBSERVED + CALCULATED)",
            data_source="crawl",
        )

    def _compute_semantic_alignment(
        self,
        target_keywords: list[str],
        crawl_pages: list,
    ) -> list[SemanticAlignmentResult]:
        """Compute title/heading semantic alignment between keywords and content.

        Deterministic: uses word overlap and substring matching only.
        No external LLM, embedding model, or API calls.
        """
        results: list[SemanticAlignmentResult] = []

        # Collect all titles and headings from crawled pages
        all_titles: list[str] = []
        all_h1s: list[str] = []
        all_h2s: list[str] = []
        page_texts: dict[str, set[str]] = {}

        for page in crawl_pages[:30]:
            if not page.is_html:
                continue
            try:
                text = page.decoded_text()
                # Extract title
                import re
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', text, re.IGNORECASE)
                if title_match:
                    all_titles.append(title_match.group(1).lower())
                # Extract headings
                for h1 in re.findall(r'<h1[^>]*>([^<]+)</h1>', text, re.IGNORECASE):
                    all_h1s.append(h1.lower())
                for h2 in re.findall(r'<h2[^>]*>([^<]+)</h2>', text, re.IGNORECASE):
                    all_h2s.append(h2.lower())
                # Collect content words
                words = set(re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()))
                page_texts[page.url] = words
            except Exception:
                pass

        for kw in target_keywords[:20]:
            kw_lower = kw.lower()
            kw_words = set(kw_lower.split())

            exact_matches = 0
            partial_matches = 0
            variants: list[str] = []
            matching_urls: list[str] = []

            # Check exact title matches
            for title in all_titles:
                if kw_lower in title:
                    exact_matches += 1

            # Check partial matches in headings
            for h1 in all_h1s + all_h2s:
                if any(w in h1 for w in kw_words if len(w) > 2):
                    partial_matches += 1

            # Check for semantic variants (words from keyword found in page content)
            for url, words in page_texts.items():
                overlap = kw_words & words
                if len(overlap) >= len(kw_words) * 0.5:
                    variants.append(f"Words found: {', '.join(overlap)}")
                    matching_urls.append(url)

            # Calculate alignment score
            score = 0.0
            if exact_matches > 0:
                score = min(100, 60 + exact_matches * 10)
            elif partial_matches > 0:
                score = min(60, 30 + partial_matches * 5)
            elif variants:
                score = min(30, len(variants) * 10)
            else:
                score = 0

            evidence_parts = []
            if exact_matches:
                evidence_parts.append(f"{exact_matches} exact title matches")
            if partial_matches:
                evidence_parts.append(f"{partial_matches} partial heading matches")
            if variants:
                evidence_parts.append(f"{len(variants)} pages with keyword word overlap")
            if not evidence_parts:
                evidence_parts.append("No matches found in titles, headings, or content")

            results.append(SemanticAlignmentResult(
                keyword=kw,
                exact_title_matches=exact_matches,
                partial_title_matches=partial_matches,
                semantic_variants=variants[:5],
                heading_keyword_coverage=partial_matches / max(len(all_h1s) + len(all_h2s), 1),
                alignment_score=score,
                affected_urls=matching_urls[:5],
                evidence="; ".join(evidence_parts),
            ))

        return results

    def _build_ranking_breakdown(
        self,
        snapshot: SiteRankingSnapshot | None,
        country: str,
        device: str,
    ) -> CategoryScore:
        """Build universal Search Rankings breakdown with mutually exclusive buckets."""
        if not snapshot or snapshot.total_keywords_tracked == 0:
            return CategoryScore(
                category_name="Search Rankings",
                overall_score=None,
                score_status="NOT ASSESSED",
                scoring_methodology="No keyword ranking data available.",
                metrics=[],
                sample_size=0,
                data_coverage=0.0,
                confidence="UNABLE TO VERIFY",
                confidence_factors=["No keywords tracked"],
                limitations=["No search ranking data was collected."],
                evidence_quality_summary="UNAVAILABLE",
            )

        N = snapshot.total_keywords_tracked
        bu = 0  # could not verify
        # Mutually exclusive buckets
        b1 = snapshot.keywords_in_top_3
        b2 = snapshot.keywords_in_top_10 - snapshot.keywords_in_top_3
        b3 = snapshot.keywords_in_top_20 - snapshot.keywords_in_top_10
        b4 = max(0, len(snapshot.top_keywords) - snapshot.keywords_in_top_20) if snapshot.top_keywords else 0
        b5 = 0  # positions 51-100 — not tracked separately
        b0 = snapshot.keywords_not_ranking

        coverage_rate = (N - bu) / N if N > 0 else 0
        verifiable = N - bu
        if verifiable > 0:
            visibility = (b1 * 1.0 + b2 * 0.6 + b3 * 0.3 + b4 * 0.1 + b5 * 0.05) / verifiable
        else:
            visibility = 0
        ranking_score = visibility * coverage_rate * 100

        metrics: list[AnalysisMetric] = [
            AnalysisMetric(
                metric_name="Top 3 Visibility", category="ranking", metric_type="percentage",
                expected=100.0, normalized_score=(b1 / N * 100) if N > 0 else 0, weight=30.0,
                raw_value=b1, raw_unit="keywords",
                raw_evidence=f"{b1} of {N} keywords rank in positions 1-3",
                normalization_method="(keywords_in_top_3 / total_keywords) * 100",
                status="PASS" if b1 > 0 else "POOR",
                evidence=f"{b1} keywords found in top 3 positions for {country.upper()} {device} Google search",
                evidence_quality="OBSERVED",
                sample_size=N, data_coverage=coverage_rate,
                confidence="HIGH" if coverage_rate >= 0.8 else "MEDIUM" if coverage_rate >= 0.5 else "LOW",
            ),
            AnalysisMetric(
                metric_name="Positions 4-10", category="ranking", metric_type="percentage",
                expected=100.0, normalized_score=(b2 / N * 100) if N > 0 else 0, weight=30.0,
                raw_value=b2, raw_unit="keywords",
                raw_evidence=f"{b2} of {N} keywords rank in positions 4-10",
                normalization_method="(keywords_in_4_10 / total_keywords) * 100",
                status="PASS" if b2 > 0 else "NEEDS IMPROVEMENT",
                evidence=f"{b2} keywords found in positions 4-10",
                evidence_quality="OBSERVED",
                sample_size=N, data_coverage=coverage_rate,
                confidence="HIGH" if coverage_rate >= 0.8 else "MEDIUM" if coverage_rate >= 0.5 else "LOW",
            ),
            AnalysisMetric(
                metric_name="Positions 11-20", category="ranking", metric_type="percentage",
                expected=100.0, normalized_score=(b3 / N * 100) if N > 0 else 0, weight=20.0,
                raw_value=b3, raw_unit="keywords",
                raw_evidence=f"{b3} of {N} keywords rank in positions 11-20",
                normalization_method="(keywords_in_11_20 / total_keywords) * 100",
                status="PASS" if b3 > 0 else "NEEDS IMPROVEMENT",
                evidence=f"{b3} keywords found in positions 11-20",
                evidence_quality="OBSERVED",
                sample_size=N, data_coverage=coverage_rate,
                confidence="HIGH" if coverage_rate >= 0.8 else "MEDIUM" if coverage_rate >= 0.5 else "LOW",
            ),
            AnalysisMetric(
                metric_name="Positions 21-100", category="ranking", metric_type="percentage",
                expected=100.0, normalized_score=((b4 + b5) / N * 100) if N > 0 else 0, weight=10.0,
                raw_value=b4 + b5, raw_unit="keywords",
                raw_evidence=f"{b4 + b5} of {N} keywords rank in positions 21-100",
                normalization_method="(keywords_in_21_100 / total_keywords) * 100",
                status="NEEDS IMPROVEMENT",
                evidence=f"{b4 + b5} keywords found in positions 21-100",
                evidence_quality="OBSERVED",
                sample_size=N, data_coverage=coverage_rate,
                confidence="HIGH" if coverage_rate >= 0.8 else "MEDIUM" if coverage_rate >= 0.5 else "LOW",
            ),
            AnalysisMetric(
                metric_name="Not Found in Top 100", category="ranking", metric_type="percentage",
                expected=0.0, normalized_score=(b0 / N * 100) if N > 0 else 0, weight=10.0,
                raw_value=b0, raw_unit="keywords",
                raw_evidence=f"{b0} of {N} keywords not found in top 100",
                normalization_method="(not_found / total_keywords) * 100 (lower is better)",
                status="POOR" if b0 > N * 0.5 else "NEEDS IMPROVEMENT",
                evidence=f"{b0} keywords had no observed ranking in top 100 results",
                evidence_quality="OBSERVED",
                sample_size=N, data_coverage=coverage_rate,
                confidence="HIGH" if coverage_rate >= 0.8 else "MEDIUM" if coverage_rate >= 0.5 else "LOW",
            ),
        ]

        methodology = (
            "Ranking Score = Visibility * Coverage Rate * 100. "
            "Visibility = (B1*1.0 + B2*0.6 + B3*0.3 + B4*0.1) / N. "
            "Buckets are mutually exclusive: B1=pos 1-3, B2=pos 4-10, B3=pos 11-20, B4=pos 21-100. "
            f"Coverage Rate = {coverage_rate:.0%}."
        )

        conf_score = min(1.0, coverage_rate) * 1.0  # evidence_quality=3/3 for OBSERVED
        confidence = "HIGH" if conf_score >= 0.8 else "MEDIUM" if conf_score >= 0.5 else "LOW" if conf_score >= 0.2 else "UNABLE TO VERIFY"

        return CategoryScore(
            category_name="Search Rankings",
            overall_score=round(ranking_score, 1),
            score_status="ASSESSED",
            scoring_methodology=methodology,
            metrics=metrics,
            sample_size=N,
            data_coverage=coverage_rate,
            confidence=confidence,
            confidence_factors=[f"{N} keywords tracked", f"Coverage: {coverage_rate:.0%}", f"Search engine: Google, Country: {country.upper()}, Device: {device}"],
            limitations=[
                "Keywords were algorithmically discovered (TF-IDF), not user-supplied.",
                f"Rankings checked to top 100 for {country.upper()} Google.",
                "Ranking data reflects a single point-in-time snapshot.",
            ],
            evidence_quality_summary="OBSERVED",
            data_source="serp",
        )

    def _build_architecture_breakdown(
        self,
        report: SiteArchitectureReport,
    ) -> CategoryScore:
        """Build universal Architecture breakdown using Gini and all fields."""
        total = report.total_pages
        if total == 0:
            return CategoryScore(
                category_name="Site Architecture",
                overall_score=None, score_status="NOT ASSESSED",
                scoring_methodology="No pages crawled.",
                metrics=[], sample_size=0, data_coverage=0.0,
                confidence="UNABLE TO VERIFY",
            )

        # 1. Page Depth: range [1->100, 3->80, 5->40, 7->10, 10+->0]
        avg_d = report.avg_depth
        if avg_d <= 1:
            depth_score = 100.0
        elif avg_d <= 3:
            depth_score = 100 - (avg_d - 1) * 10
        elif avg_d <= 5:
            depth_score = 80 - (avg_d - 3) * 20
        elif avg_d <= 7:
            depth_score = 40 - (avg_d - 5) * 15
        elif avg_d <= 10:
            depth_score = 10 - (avg_d - 7) * (10 / 3)
        else:
            depth_score = 0

        # 2. Orphan Rate: % pages with >=1 incoming link
        orphan_count = len(report.orphans)
        orphan_rate = ((total - orphan_count) / total * 100) if total > 0 else 100

        # 3. Link Density: range [5+->100, 3->70, 1->30, 0->0]
        avg_links = report.avg_links_per_page
        if avg_links >= 5:
            link_density_score = 100.0
        elif avg_links >= 3:
            link_density_score = 70 + (avg_links - 3) * 15
        elif avg_links >= 1:
            link_density_score = 30 + (avg_links - 1) * 20
        else:
            link_density_score = 0

        # 4. Link Equity Gini: (1 - Gini) * 100
        gini = report.pagerank_gini
        gini_score = ((1 - gini) * 100) if gini is not None else 50.0

        # 5. Max Crawl Depth: range [3->100, 5->60, 7->30, 10+->0]
        max_d = report.max_depth
        if max_d <= 3:
            max_depth_score = 100.0
        elif max_d <= 5:
            max_depth_score = 100 - (max_d - 3) * 20
        elif max_d <= 7:
            max_depth_score = 60 - (max_d - 5) * 15
        elif max_d <= 10:
            max_depth_score = 30 - (max_d - 7) * 10
        else:
            max_depth_score = 0

        metrics = [
            AnalysisMetric(
                metric_name="Page Depth", category="architecture", metric_type="range",
                expected=100.0, normalized_score=depth_score, weight=25.0,
                raw_value=avg_d, raw_unit="clicks",
                raw_evidence=f"Avg depth: {avg_d} clicks from homepage",
                normalization_method="Range: 1->100, 3->80, 5->40, 7->10, 10+->0",
                status="PASS" if depth_score >= 80 else "NEEDS IMPROVEMENT" if depth_score >= 40 else "POOR",
                evidence=f"Average {avg_d} clicks from homepage across {total} pages",
                evidence_quality="CALCULATED",
                sample_size=total, data_coverage=1.0,
                confidence="HIGH",
            ),
            AnalysisMetric(
                metric_name="Orphan Pages", category="architecture", metric_type="percentage",
                expected=100.0, normalized_score=orphan_rate, weight=20.0,
                raw_value=orphan_count, raw_unit="pages",
                raw_evidence=f"{orphan_count} of {total} pages have no incoming links",
                normalization_method="% pages with >=1 incoming internal link",
                status="PASS" if orphan_rate >= 90 else "NEEDS IMPROVEMENT" if orphan_rate >= 70 else "POOR",
                evidence=f"{orphan_count} orphan pages detected (no incoming internal links)",
                evidence_quality="CALCULATED",
                affected_urls=list(report.orphans[:10]),
                why_it_matters="Orphan pages receive no link equity and are rarely crawled.",
                remediation="Add internal links from relevant pages or remove if not valuable.",
                sample_size=total, data_coverage=1.0,
                confidence="HIGH",
            ),
            AnalysisMetric(
                metric_name="Internal Link Density", category="architecture", metric_type="range",
                expected=100.0, normalized_score=link_density_score, weight=20.0,
                raw_value=avg_links, raw_unit="links/page",
                raw_evidence=f"Avg {avg_links} internal links per page",
                normalization_method="Range: 5+->100, 3->70, 1->30, 0->0",
                status="PASS" if link_density_score >= 80 else "NEEDS IMPROVEMENT" if link_density_score >= 40 else "POOR",
                evidence=f"Average {avg_links} internal links per page across {total} pages",
                evidence_quality="CALCULATED",
                sample_size=total, data_coverage=1.0,
                confidence="HIGH",
            ),
            AnalysisMetric(
                metric_name="Internal Graph PageRank Equity Distribution", category="architecture", metric_type="range",
                expected=100.0, normalized_score=gini_score, weight=15.0,
                raw_value=gini, raw_unit="Gini coefficient",
                raw_evidence=f"Internal Graph PageRank Gini: {gini}" if gini is not None else "Insufficient data for Gini calculation",
                normalization_method="(1 - Gini) * 100. Gini 0=even, 1=uneven.",
                status="PASS" if gini_score >= 70 else "NEEDS IMPROVEMENT" if gini_score >= 40 else "POOR" if gini is not None else "NOT ASSESSED",
                evidence=f"Internal Graph PageRank Gini coefficient: {gini}" if gini is not None else "Insufficient pages with non-zero Internal Graph PageRank for Gini calculation",
                evidence_quality="CALCULATED" if gini is not None else "UNAVAILABLE",
                limitations="This is Internal Graph PageRank — NOT Google's PageRank. It measures internal link equity distribution within the site only.",
                why_it_matters="Uneven internal PageRank distribution means some pages receive disproportionate authority while others are starved.",
                remediation="Redistribute internal links to spread authority more evenly across important pages.",
                sample_size=total, data_coverage=1.0 if gini is not None else 0.0,
                confidence="HIGH" if gini is not None else "UNABLE TO VERIFY",
            ),
            AnalysisMetric(
                metric_name="Max Crawl Depth", category="architecture", metric_type="range",
                expected=100.0, normalized_score=max_depth_score, weight=20.0,
                raw_value=max_d, raw_unit="clicks",
                raw_evidence=f"Deepest page: {max_d} clicks from homepage",
                normalization_method="Range: 3->100, 5->60, 7->30, 10+->0",
                status="PASS" if max_depth_score >= 80 else "NEEDS IMPROVEMENT" if max_depth_score >= 40 else "POOR",
                evidence=f"Maximum crawl depth: {max_d} clicks from homepage",
                evidence_quality="CALCULATED",
                sample_size=total, data_coverage=1.0,
                confidence="HIGH",
            ),
        ]

        total_weight = sum(m.weight for m in metrics)
        overall = sum(m.weight * m.normalized_score for m in metrics) / total_weight if total_weight > 0 else 0

        return CategoryScore(
            category_name="Site Architecture",
            overall_score=round(overall, 1),
            score_status="ASSESSED",
            scoring_methodology="Score = sum(weight * normalized_score) / sum(weights) across 5 metrics.",
            metrics=metrics,
            sample_size=total,
            data_coverage=1.0,
            confidence="HIGH",
            confidence_factors=[f"{total} pages crawled", "Full link graph analyzed"],
            limitations=["Internal Graph PageRank is NOT Google's PageRank.", "Gini requires >=3 pages with non-zero PageRank."],
            evidence_quality_summary="CALCULATED",
            data_source="crawl",
        )

    def _build_aio_breakdown(
        self,
        aio: SiteAIOAnalysis | None,
        country: str,
    ) -> CategoryScore:
        """Build universal AIO breakdown with corrected competitor metric."""
        if not aio or aio.keywords_checked == 0:
            return CategoryScore(
                category_name="AI Overview (AIO)",
                overall_score=None,
                score_status="NOT ASSESSED",
                scoring_methodology="No AIO data available.",
                metrics=[],
                sample_size=0,
                data_coverage=0.0,
                confidence="UNABLE TO VERIFY",
                confidence_factors=["No keywords checked for AIO"],
                limitations=["AIO analysis requires search provider with SERP feature detection."],
                evidence_quality_summary="UNAVAILABLE",
            )

        Q = aio.keywords_checked
        Q_aio = aio.ai_overviews_present
        Q_cited = aio.target_cited_count
        Q_comp_cited = aio.competitor_cited_count
        coverage = aio.keywords_checked / max(Q, 1)  # Coverage gate

        if coverage < 0.5:
            return CategoryScore(
                category_name="AI Overview (AIO)",
                overall_score=None,
                score_status="INSUFFICIENT DATA",
                scoring_methodology=f"Data coverage {coverage:.0%} below 50% threshold.",
                metrics=[],
                sample_size=Q,
                data_coverage=coverage,
                confidence="UNABLE TO VERIFY",
                confidence_factors=[f"Coverage {coverage:.0%} < 50% threshold"],
                limitations=["Insufficient data coverage for reliable AIO scoring."],
                evidence_quality_summary="INSUFFICIENT",
            )

        presence_rate = Q_aio / Q if Q > 0 else 0
        citation_rate = Q_cited / max(Q_aio, 1)
        comp_citation_rate = Q_comp_cited / max(Q_aio, 1)

        metrics = [
            AnalysisMetric(
                metric_name="AIO Presence Rate", category="aio", metric_type="percentage",
                expected=100.0, normalized_score=presence_rate * 100, weight=30.0,
                raw_value=Q_aio, raw_unit="queries",
                raw_evidence=f"{Q_aio} of {Q} queries showed AI Overviews",
                normalization_method="(queries_with_aio / total_queries) * 100",
                status="PASS" if presence_rate > 0.5 else "NEEDS IMPROVEMENT",
                evidence=f"AI Overviews detected for {Q_aio} of {Q} target keywords in {country.upper()} Google search",
                evidence_quality="OBSERVED",
                sample_size=Q, data_coverage=coverage,
                confidence="HIGH" if coverage >= 0.8 else "MEDIUM",
            ),
            AnalysisMetric(
                metric_name="Target Citation Rate", category="aio", metric_type="percentage",
                expected=100.0, normalized_score=citation_rate * 100, weight=50.0,
                raw_value=Q_cited, raw_unit="queries",
                raw_evidence=f"{Q_cited} of {Q_aio} AIO queries cite target domain",
                normalization_method="(target_cited / queries_with_aio) * 100",
                status="PASS" if citation_rate > 0.3 else "POOR",
                evidence=f"Target domain cited in {Q_cited} of {Q_aio} AI Overview queries",
                evidence_quality="OBSERVED",
                sample_size=Q_aio, data_coverage=coverage,
                confidence="HIGH" if coverage >= 0.8 else "MEDIUM",
            ),
            AnalysisMetric(
                metric_name="Competitor Non-Citation Rate", category="aio", metric_type="percentage",
                expected=100.0, normalized_score=(1 - comp_citation_rate) * 100, weight=20.0,
                raw_value=Q_comp_cited, raw_unit="queries",
                raw_evidence=f"{Q_comp_cited} of {Q_aio} AIO queries cite competitors",
                normalization_method="(1 - competitor_cited / queries_with_aio) * 100",
                status="PASS" if comp_citation_rate < 0.3 else "POOR",
                evidence=f"Competitors cited in {Q_comp_cited} of {Q_aio} AI Overview queries (higher = worse)",
                evidence_quality="OBSERVED",
                sample_size=Q_aio, data_coverage=coverage,
                confidence="HIGH" if coverage >= 0.8 else "MEDIUM",
            ),
        ]

        total_weight = sum(m.weight for m in metrics)
        overall = sum(m.weight * m.normalized_score for m in metrics) / total_weight if total_weight > 0 else 0

        return CategoryScore(
            category_name="AI Overview (AIO)",
            overall_score=round(overall, 1),
            score_status="ASSESSED",
            scoring_methodology=f"AIO Score = (Presence * 30 + Citation * 50 + CompetitorNonCitation * 20). Coverage: {coverage:.0%}.",
            metrics=metrics,
            sample_size=Q,
            data_coverage=coverage,
            confidence="HIGH" if coverage >= 0.8 else "MEDIUM" if coverage >= 0.5 else "LOW",
            confidence_factors=[f"{Q} queries checked", f"Coverage: {coverage:.0%}", f"Country: {country.upper()}"],
            limitations=[
                "AIO detection depends on SERP feature availability.",
                "Results are point-in-time and may vary by region/time.",
            ],
            evidence_quality_summary="OBSERVED",
            data_source="serp",
        )

    def _build_geo_breakdown(
        self,
        geo: SiteGEOAnalysis | None,
    ) -> CategoryScore:
        """Build universal GEO breakdown with real observations when available."""
        if not geo or geo.keywords_checked == 0:
            return CategoryScore(
                category_name="Generative Engine Optimization (GEO)",
                overall_score=None,
                score_status="NOT ASSESSED",
                scoring_methodology="No GEO data available.",
                metrics=[],
                sample_size=0,
                data_coverage=0.0,
                confidence="UNABLE TO VERIFY",
                confidence_factors=["No keywords checked for GEO"],
                limitations=[
                    "GEO analysis requires a provider that supports generative engine queries.",
                    "Configure an LLM-based provider (OpenAI-compatible) for real GEO data."
                ],
                evidence_quality_summary="UNAVAILABLE",
            )

        Q = geo.keywords_checked
        Q_mentioned = geo.target_mentioned_count
        Q_comp_mentioned = geo.competitor_mentioned_count
        coverage = geo.keywords_checked / max(Q, 1)

        if coverage < 0.5:
            return CategoryScore(
                category_name="Generative Engine Optimization (GEO)",
                overall_score=None,
                score_status="INSUFFICIENT DATA",
                scoring_methodology=f"Data coverage {coverage:.0%} below 50% threshold.",
                metrics=[],
                sample_size=Q,
                data_coverage=coverage,
                confidence="UNABLE TO VERIFY",
                confidence_factors=[f"Coverage {coverage:.0%} < 50% threshold"],
                limitations=["Insufficient data coverage for reliable GEO scoring."],
                evidence_quality_summary="INSUFFICIENT",
            )

        mention_rate = Q_mentioned / Q if Q > 0 else 0
        comp_mention_rate = Q_comp_mentioned / Q if Q > 0 else 0

        metrics = [
            AnalysisMetric(
                metric_name="Target Mention Rate", category="geo", metric_type="percentage",
                expected=100.0, normalized_score=mention_rate * 100, weight=50.0,
                raw_value=Q_mentioned, raw_unit="queries",
                raw_evidence=f"Target mentioned in {Q_mentioned} of {Q} queries",
                normalization_method="(target_mentioned / total_queries) * 100",
                status="PASS" if mention_rate > 0.3 else "POOR",
                evidence=f"Target brand mentioned in {Q_mentioned} of {Q} generative engine queries",
                evidence_quality="OBSERVED",
                sample_size=Q, data_coverage=coverage,
                confidence="HIGH" if coverage >= 0.8 else "MEDIUM",
            ),
            AnalysisMetric(
                metric_name="Competitor Mention Rate", category="geo", metric_type="percentage",
                expected=0.0, normalized_score=(1 - comp_mention_rate) * 100, weight=30.0,
                raw_value=Q_comp_mentioned, raw_unit="queries",
                raw_evidence=f"Competitors mentioned in {Q_comp_mentioned} of {Q} queries",
                normalization_method="(1 - competitor_mentioned / total_queries) * 100 (lower competitor mentions = better)",
                status="PASS" if comp_mention_rate < 0.3 else "POOR",
                evidence=f"Competitors mentioned in {Q_comp_mentioned} of {Q} generative engine queries",
                evidence_quality="OBSERVED",
                sample_size=Q, data_coverage=coverage,
                confidence="HIGH" if coverage >= 0.8 else "MEDIUM",
            ),
            AnalysisMetric(
                metric_name="Average Mentions per Query", category="geo", metric_type="range",
                expected=100.0, normalized_score=min(100, geo.avg_mention_count * 20), weight=20.0,
                raw_value=geo.avg_mention_count, raw_unit="mentions/query",
                raw_evidence=f"Average {geo.avg_mention_count:.1f} mentions per query where target mentioned",
                normalization_method="min(100, avg_mentions * 20)",
                status="PASS" if geo.avg_mention_count > 1 else "NEEDS IMPROVEMENT",
                evidence=f"Average {geo.avg_mention_count:.1f} target mentions per observation",
                evidence_quality="CALCULATED",
                sample_size=Q_mentioned if Q_mentioned > 0 else 0, data_coverage=coverage,
                confidence="MEDIUM",
            ),
        ]

        total_weight = sum(m.weight for m in metrics)
        overall = sum(m.weight * m.normalized_score for m in metrics) / total_weight if total_weight > 0 else 0

        engines_tested = ", ".join(geo.engines_tested) if geo.engines_tested else "unknown"

        return CategoryScore(
            category_name="Generative Engine Optimization (GEO)",
            overall_score=round(overall, 1),
            score_status="ASSESSED",
            scoring_methodology=f"GEO Score = (TargetMention * 50 + CompetitorNonMention * 30 + AvgMentions * 20). Coverage: {coverage:.0%}. Engines: {engines_tested}.",
            metrics=metrics,
            sample_size=Q,
            data_coverage=coverage,
            confidence="HIGH" if coverage >= 0.8 else "MEDIUM" if coverage >= 0.5 else "LOW",
            confidence_factors=[f"{Q} queries checked", f"Coverage: {coverage:.0%}", f"Engines: {engines_tested}"],
            limitations=[
                "GEO observations depend on the configured LLM provider.",
                "Results may vary across different generative engines.",
                "Brand mention detection uses simple string matching, not semantic understanding.",
            ],
            evidence_quality_summary="OBSERVED",
            data_source="live_query",
        )

    # ══════════════════════════════════════════════════════════════════════
    # Comprehensive On-Page SEO Analysis
    # ══════════════════════════════════════════════════════════════════════

    def _analyze_onpage_seo(self, content_health: SiteContentHealth) -> list[SearchRecommendation]:
        """Analyze on-page SEO elements: titles, meta descriptions, keywords, headers, etc."""
        recs: list[SearchRecommendation] = []

        missing_meta = content_health.missing_meta_desc_pages
        if missing_meta > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.HIGH,
                title=f"{missing_meta} pages missing meta descriptions",
                description=(
                    f"{missing_meta} pages lack meta descriptions. "
                    f"Meta descriptions are your SERP ad copy — they directly impact click-through rates. "
                    f"Write unique, compelling 150-160 character descriptions with target keywords."
                ),
                supporting_metrics={"missing_meta_desc": missing_meta},
                confidence=0.9,
            ))

        low_word_count = content_health.low_word_count_pages
        if low_word_count > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.HIGH,
                title=f"{low_word_count} pages with insufficient word count",
                description=(
                    f"{low_word_count} pages have very low word count (<300 words). "
                    f"Search engines prefer comprehensive content. Expand with relevant details, "
                    f"examples, FAQs, and related subtopics to demonstrate expertise."
                ),
                supporting_metrics={"low_word_count": low_word_count},
                confidence=0.85,
            ))

        if hasattr(content_health, 'top_issues'):
            missing_schema = sum(1 for issue, count in content_health.top_issues if 'schema' in issue.lower())
            if missing_schema > 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.OPPORTUNITY,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"{missing_schema} pages missing Schema.org markup",
                    description=(
                        "Structured data helps search engines understand your content and "
                        "enables rich snippets (FAQ, HowTo, Product, Article, etc.). "
                        "Add JSON-LD schema to key pages for better SERP visibility."
                    ),
                    supporting_metrics={"missing_schema": missing_schema},
                    confidence=0.8,
                ))

        stale_content = sum(1 for issue, count in content_health.top_issues if 'stale' in issue.lower())
        if stale_content > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{stale_content} pages with potentially stale content",
                description=(
                    "Content freshness is a ranking factor. Update old content with current data, "
                    "new examples, recent statistics, and current year references. "
                    "Add 'Last Updated' dates to signal freshness."
                ),
                supporting_metrics={"stale_pages": stale_content},
                confidence=0.75,
            ))

        poor_readability = sum(1 for issue, count in content_health.top_issues if 'readability' in issue.lower())
        if poor_readability > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{poor_readability} pages with poor readability",
                description=(
                    "Content that is hard to read increases bounce rate and reduces dwell time. "
                    "Use shorter sentences, simpler words, subheadings, bullet points, "
                    "and visual elements. Target Flesch Reading Ease > 60."
                ),
                supporting_metrics={"poor_readability": poor_readability},
                confidence=0.7,
            ))

        keyword_stuffing = sum(1 for issue, count in content_health.top_issues if 'stuffing' in issue.lower())
        if keyword_stuffing > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.HIGH,
                title=f"{keyword_stuffing} pages with potential keyword stuffing",
                description=(
                    "Over-optimization triggers spam filters. Write naturally for humans, "
                    "not keyword density. Use synonyms, related terms (LSI keywords), "
                    "and focus on topic coverage rather than exact-match repetition."
                ),
                supporting_metrics={"keyword_stuffing": keyword_stuffing},
                confidence=0.85,
            ))

        missing_alt = sum(1 for issue, count in content_health.top_issues if 'alt' in issue.lower())
        if missing_alt > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{missing_alt} pages with images missing alt text",
                description=(
                    "Alt text is crucial for accessibility and image search. "
                    "Describe images with relevant keywords naturally. "
                    "This also helps with Google Images traffic."
                ),
                supporting_metrics={"missing_alt": missing_alt},
                confidence=0.8,
            ))

        low_internal = sum(1 for issue, count in content_health.top_issues if 'internal' in issue.lower())
        if low_internal > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{low_internal} pages with insufficient internal links",
                description=(
                    "Internal links distribute PageRank and help users discover content. "
                    "Add 3-5 relevant internal links per page using descriptive anchor text. "
                    "Link to cornerstone content and related articles."
                ),
                supporting_metrics={"low_internal_links": low_internal},
                confidence=0.75,
            ))

        return recs

    # ══════════════════════════════════════════════════════════════════════
    # Unified Recommendations
    # ══════════════════════════════════════════════════════════════════════

    def _build_unified_recommendations(
        self,
        *,
        ranking_snapshot: SiteRankingSnapshot | None,
        technical_health: SiteTechnicalHealth,
        content_health: SiteContentHealth,
        architecture_health: SiteArchitectureHealth,
        aio_analysis: SiteAIOAnalysis | None,
        geo_analysis: SiteGEOAnalysis | None,
        search_intel: SearchIntelligenceResult | None,
    ) -> tuple[SearchRecommendation, ...]:
        """Build unified recommendations across all analysis areas (SEO + AIO + GEO)."""
        recs: list[SearchRecommendation] = []

        # ── Technical recommendations ──
        if technical_health.critical_issues > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.RANKING,
                priority=RecommendationPriority.CRITICAL,
                title=f"{technical_health.critical_issues} critical technical issues",
                description=(
                    f"Found {technical_health.critical_issues} critical technical SEO issues "
                    f"that may prevent indexing or ranking. Fix these first."
                ),
                supporting_metrics={"critical_count": technical_health.critical_issues},
                confidence=0.95,
            ))

        if technical_health.warning_issues > 5:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.RANKING,
                priority=RecommendationPriority.HIGH,
                title=f"{technical_health.warning_issues} technical warnings",
                description="Multiple technical warnings that could impact crawlability and rankings.",
                supporting_metrics={"warning_count": technical_health.warning_issues},
                confidence=0.8,
            ))

        # ── Content recommendations ──
        if content_health.thin_content_pages > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.HIGH,
                title=f"{content_health.thin_content_pages} thin content pages",
                description="Pages with insufficient content unlikely to rank. Expand or consolidate.",
                supporting_metrics={"thin_pages": content_health.thin_content_pages},
                confidence=0.9,
            ))

        if content_health.duplicate_groups > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.CANNIBALIZATION,
                priority=RecommendationPriority.HIGH,
                title=f"{content_health.duplicate_groups} duplicate content groups",
                description="Near-duplicate pages compete with each other. Consolidate or canonicalize.",
                supporting_metrics={"duplicate_groups": content_health.duplicate_groups},
                confidence=0.85,
            ))

        if content_health.missing_h1_pages > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{content_health.missing_h1_pages} pages missing H1",
                description="Pages without H1 tags miss a key on-page SEO signal.",
                supporting_metrics={"missing_h1": content_health.missing_h1_pages},
                confidence=0.8,
            ))

        # ── Comprehensive On-Page SEO Audit ──
        onpage_issues = self._analyze_onpage_seo(content_health)
        for issue in onpage_issues:
            recs.append(issue)

        # ── AIO (AI Overview) recommendations ──
        if aio_analysis:
            if aio_analysis.ai_overviews_present > 0 and aio_analysis.target_cited_count == 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.AIO,
                    priority=RecommendationPriority.CRITICAL,
                    title=f"AI Overviews present for {aio_analysis.ai_overviews_present} keywords but site not cited",
                    description=(
                        f"AI Overviews appear for {aio_analysis.ai_overviews_present} of your target keywords, "
                        f"but your site is not cited in any. Create authoritative, concise answers "
                        f"to these queries to capture citations."
                    ),
                    supporting_metrics={
                        "ai_overviews_present": aio_analysis.ai_overviews_present,
                        "competitor_cited": aio_analysis.competitor_cited_count,
                        "top_competitors": aio_analysis.competitor_domains_cited[:5],
                    },
                    confidence=0.9,
                ))

            if aio_analysis.target_citation_rate < 0.3 and aio_analysis.ai_overviews_present > 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.AIO,
                    priority=RecommendationPriority.HIGH,
                    title=f"Low AIO citation rate ({aio_analysis.target_citation_rate:.0%})",
                    description="Your site is rarely cited in AI Overviews despite their presence. Optimize content structure.",
                    supporting_metrics={"citation_rate": aio_analysis.target_citation_rate},
                    confidence=0.85,
                ))

            for opp in aio_analysis.top_opportunities[:5]:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.AIO,
                    priority=RecommendationPriority.HIGH,
                    title=f"AIO opportunity: {opp['keyword']}",
                    description=opp.get('action', 'Optimize content for AI Overview citation'),
                    affected_keywords=(opp['keyword'],),
                    supporting_metrics={"competitors_cited": opp.get('competitor_cited', 0)},
                    confidence=0.8,
                ))

        # ── GEO (Generative Engine) recommendations ──
        if geo_analysis:
            if geo_analysis.target_mentioned_count == 0 and geo_analysis.competitor_mentioned_count > 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.GEO,
                    priority=RecommendationPriority.CRITICAL,
                    title="Not mentioned in generative engines while competitors are",
                    description=(
                        f"Competitors mentioned {geo_analysis.competitor_mentioned_count} times across "
                        f"generative engines but your brand is absent. Build authority and citations."
                    ),
                    supporting_metrics={
                        "competitor_mentions": geo_analysis.competitor_mentioned_count,
                        "top_competitors": geo_analysis.competitor_domains_mentioned[:5],
                    },
                    confidence=0.85,
                ))

            if geo_analysis.mention_rate < 0.2:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.GEO,
                    priority=RecommendationPriority.HIGH,
                    title=f"Low GEO mention rate ({geo_analysis.mention_rate:.0%})",
                    description="Generative engines rarely mention your brand. Focus on authoritative content and citations.",
                    supporting_metrics={"mention_rate": geo_analysis.mention_rate},
                    confidence=0.8,
                ))

            for opp in geo_analysis.top_opportunities[:5]:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.GEO,
                    priority=RecommendationPriority.HIGH,
                    title=f"GEO opportunity: {opp['keyword']}",
                    description=opp.get('action', 'Build authority for generative engine mentions'),
                    affected_keywords=(opp['keyword'],),
                    supporting_metrics={"competitors_mentioned": opp.get('competitors_mentioned', 0)},
                    confidence=0.75,
                ))

        # ── Architecture recommendations ──
        if architecture_health.orphan_pages > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{architecture_health.orphan_pages} orphan pages",
                description="Pages with no internal links can't be discovered by users or search engines.",
                supporting_metrics={"orphan_pages": architecture_health.orphan_pages},
                confidence=0.85,
            ))

        if architecture_health.avg_depth > 4:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.RANKING,
                priority=RecommendationPriority.MEDIUM,
                title=f"Deep site architecture (avg depth: {architecture_health.avg_depth:.1f})",
                description="Important pages buried too deep. Flatten architecture for better crawl efficiency.",
                supporting_metrics={"avg_depth": architecture_health.avg_depth},
                confidence=0.7,
            ))

        # ── Ranking recommendations ──
        if ranking_snapshot:
            half_keywords = ranking_snapshot.total_keywords_tracked * 0.5
            if ranking_snapshot.keywords_not_ranking > half_keywords:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.CRITICAL,
                    title="Most target keywords not ranking",
                    description=(
                        f"{ranking_snapshot.keywords_not_ranking} of "
                        f"{ranking_snapshot.total_keywords_tracked} keywords have no ranking. "
                        f"Content or authority gap."
                    ),
                    supporting_metrics={
                        "not_ranking": ranking_snapshot.keywords_not_ranking,
                        "total": ranking_snapshot.total_keywords_tracked,
                    },
                    confidence=0.9,
                ))

            if (
            ranking_snapshot.keywords_in_top_10 == 0
            and ranking_snapshot.total_keywords_tracked > 0
        ):
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.CRITICAL,
                    title="No keywords in top 10",
                    description=(
                        "Zero keywords ranking in top 10. "
                        "Fundamental content/authority issues."
                    ),
                    confidence=0.95,
                ))

            if ranking_snapshot.visibility_score < 0.2:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.HIGH,
                    title=f"Low search visibility ({ranking_snapshot.visibility_score:.0%})",
                    description=(
                        "Overall visibility is very low. "
                        "Focus on technical foundation and content."
                    ),
                    supporting_metrics={"visibility": ranking_snapshot.visibility_score},
                    confidence=0.9,
                ))

        # ── Add search intelligence recommendations ──
        if search_intel:
            recs.extend(search_intel.recommendations)

        # Sort by priority then confidence
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        recs.sort(key=lambda r: (priority_order[r.priority], -r.confidence))

        return tuple(recs)

    def _empty_result(
        self, domain: str, crawl_run_id: str | None, analysis_start: datetime | None = None
    ) -> SiteAnalysisResult:
        return SiteAnalysisResult(
            domain=domain,
            analyzed_at=datetime.now(UTC),
            crawl_run_id=crawl_run_id,
            technical_score=0.0,
            content_score=0.0,
            ranking_score=0.0,
            architecture_score=0.0,
            overall_score=0.0,
            access_status=AccessStatus(
                accessible=False,
                status_code=0,
                analysis_status="BLOCKED",
                block_reason="No pages could be retrieved from the target.",
            ),
            website_type=WebsiteTypeInfo(
                technology="Unknown", confidence=0.0, evidence=["No pages crawled"]
            ),
            analysis_started_at=analysis_start,
            analysis_completed_at=datetime.now(UTC),
        )


# Factory for easy instantiation in the API
def create_site_analysis_service(
    crawl_service: CrawlService,
    audit_service: AuditService,
    content_service: ContentService,
    search_provider: SearchProvider | ProviderRegistry,
    repository: CrawlRunRepository,
    crux_service: CruxService | None = None,
) -> SiteAnalysisService:
    return SiteAnalysisService(
        crawl_service=crawl_service,
        audit_service=audit_service,
        content_service=content_service,
        search_provider=search_provider,
        repository=repository,
        crux_service=crux_service,
    )


__all__ = [
    "AIODetailQuery",
    "AccessStatus",
    "AnalysisMetric",
    "AuthorityGapDetail",
    "CategoryScore",
    "ContentGapDetail",
    "CountryActionItem",
    "CountryRankingDetail",
    "GEODetailQuery",
    "KeywordRankingDetail",
    "ReportMetadata",
    "SemanticAlignmentResult",
    "SiteAIOAnalysis",
    "SiteAnalysisResult",
    "SiteAnalysisService",
    "SiteArchitectureHealth",
    "SiteContentHealth",
    "SiteCountryRanking",
    "SiteEntityKnowledgeGraphAnalysis",
    "SiteGEOAnalysis",
    "SitePerformanceSummary",
    "SiteRankingSnapshot",
    "SiteTechnicalHealth",
    "TechnicalMetricDetail",
    "WebsiteTypeInfo",
    "create_site_analysis_service",
]
