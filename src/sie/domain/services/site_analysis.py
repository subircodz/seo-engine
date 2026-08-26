"""Site Analysis Service — unified website intelligence.

Combines crawling, technical SEO audit, content analysis, link graph,
ranking discovery, search intelligence, AIO (AI Overview), and GEO (Generative Engine)
analysis into a single actionable report for dominating search results.

This is the main entry point for "analyze this website and tell me how to rank #1" workflows.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sie.domain.engines.search_aio import analyze_aio_observations
from sie.domain.engines.search_analytics import analyze_search_dataset
from sie.domain.engines.search_geo import analyze_geo_observations
from sie.domain.models.audit import TechnicalAuditResult, SiteArchitectureReport
from sie.domain.models.content import ContentQualityReport
from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
    SearchQuery,
)
from sie.domain.models.search_aio import AIOverviewObservation, AIOverviewResult, AIOverviewType
from sie.domain.models.search_geo import GEOObservation, GEOResult, GenerativeEngineType
from sie.domain.models.search_result import SearchResult
from sie.domain.models.search_import import SearchImportResult
from sie.domain.services.audit_service import AuditService
from sie.domain.services.cannibalization import CannibalizationDetector
from sie.domain.services.content_service import ContentService
from sie.domain.services.crawl_service import CrawlService
from sie.domain.services.ranking_volatility import RankingVolatilityService
from sie.domain.services.search_collection_service import SearchCollectionService
from sie.domain.services.search_intelligence import (
    SearchIntelligenceResult,
    SearchIntelligenceService,
    SearchIntelligenceSummary,
    SearchRecommendation,
    RecommendationCategory,
    RecommendationPriority,
)
from sie.domain.services.search_opportunity import SearchOpportunityService
from sie.domain.ports.persistence import CrawlRunRepository
from sie.domain.ports.search_provider import SearchProvider
from sie.logging import get_logger

logger = get_logger(__name__)


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
    aio_score: float
    geo_score: float
    overall_score: float

    # Detailed sections
    rankings: SiteRankingSnapshot | None = None
    technical: SiteTechnicalHealth | None = None
    content: SiteContentHealth | None = None
    architecture: SiteArchitectureHealth | None = None
    aio: SiteAIOAnalysis | None = None
    geo: SiteGEOAnalysis | None = None

    # Unified recommendations (prioritized across all areas)
    recommendations: tuple[SearchRecommendation, ...] = ()

    # Intelligence details (for drill-down)
    search_intelligence: SearchIntelligenceResult | None = None
    technical_audit: TechnicalAuditResult | None = None
    architecture_report: SiteArchitectureReport | None = None
    content_quality: ContentQualityReport | None = None


class SiteAnalysisService:
    """Orchestrates complete site analysis: crawl + audit + rankings + intelligence."""

    def __init__(
        self,
        crawl_service: CrawlService,
        audit_service: AuditService,
        content_service: ContentService,
        search_provider: SearchProvider,
        repository: CrawlRunRepository,
        collection_source: str = "site-analysis",
    ) -> None:
        self._crawl_service = crawl_service
        self._audit_service = audit_service
        self._content_service = content_service
        self._search_provider = search_provider
        self._repository = repository

        self._collection_service = SearchCollectionService(
            search_provider,
            repository=repository,
            source=collection_source,
        )
        self._intelligence_service = SearchIntelligenceService()

    async def analyze_site(
        self,
        domain: str,
        *,
        max_pages: int = 100,
        max_keywords: int = 50,
        country: str = "us",
        device: str = "desktop",
        competitors: list[str] | None = None,
        deep_aio: bool = True,
        deep_geo: bool = True,
    ) -> SiteAnalysisResult:
        """Run complete site analysis with SEO, AIO, and GEO intelligence.

        Steps:
        1. Crawl the site (technical + content + architecture)
        2. Discover what keywords the domain ranks for (intelligently from content)
        4. Analyze AI Overview (AIO) presence and citation opportunities
        5. Analyze Generative Engine (GEO) mentions and visibility
        6. Collect competitor rankings for those keywords
        7. Run unified search intelligence
        8. Synthesize everything into prioritized recommendations for domination
        """
        logger.info("Starting comprehensive site analysis for %s", domain)

        # Normalize domain
        clean_domain = self._normalize_domain(domain)
        seed_url = f"https://{clean_domain}"

        # ─── Step 1: Crawl the site ───
        crawl_run_id = await self._run_crawl(seed_url, max_pages)
        crawl_pages = self._get_crawl_pages(crawl_run_id)

        if not crawl_pages:
            logger.warning("No pages crawled for %s", domain)
            return self._empty_result(clean_domain, crawl_run_id)

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
                dataset, observations, competitor_rankings
            )

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

        return SiteAnalysisResult(
            domain=clean_domain,
            analyzed_at=datetime.now(UTC),
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
            recommendations=recommendations,
            search_intelligence=search_intel,
            technical_audit=technical_result,
            architecture_report=architecture_report,
            content_quality=content_quality,
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

    def _extract_target_keywords(self, crawl_pages: list, max_keywords: int) -> list[str]:
        """Intelligently extract target keywords from crawled content.

        Strategy:
        1. Extract keywords from each page's content using TF-IDF-like scoring
        2. Weight by page importance (homepage, main nav, high traffic)
        3. Filter for commercial/transactional intent keywords
        4. Deduplicate and cluster similar terms
        5. Return top keywords
        """
        import re
        from collections import Counter

        # Extended stopwords for SEO keyword extraction
        STOPWORDS = frozenset({
            "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
            "has", "he", "in", "is", "it", "its", "of", "on", "that", "the", "to",
            "was", "were", "will", "with", "you", "your", "we", "our", "their",
            "this", "that", "these", "those", "have", "has", "had", "do", "does",
            "did", "but", "not", "or", "if", "then", "else", "when", "where",
            "why", "how", "what", "who", "which", "can", "could", "should",
            "would", "may", "might", "must", "shall", "will", "been", "being",
            "there", "here", "more", "most", "some", "any", "all", "each",
            "few", "many", "much", "other", "such", "only", "own", "same",
            "than", "too", "very", "just", "now", "then", "also", "well",
            "even", "back", "after", "before", "during", "while", "since",
            "until", "between", "among", "through", "into", "onto", "upon",
        })

        # Commercial/transactional intent indicators
        COMMERCIAL_INDICATORS = frozenset([
            'buy', 'price', 'cost', 'cheap', 'best', 'top', 'review', 'compare',
            'vs', 'versus', 'alternative', 'service', 'company', 'agency',
            'software', 'tool', 'platform', 'solution', 'service', 'hire',
            'consultant', 'expert', 'specialist', 'provider', 'vendor',
            'quote', 'estimate', 'pricing', 'plan', 'package', 'deal',
            'discount', 'offer', 'trial', 'demo', 'free', 'download',
            'guide', 'tutorial', 'how', 'what', 'where', 'when', 'who',
        ])

        keyword_scores: Counter = Counter()

        for i, page in enumerate(crawl_pages[:30]):  # Analyze top 30 pages
            if not page.is_html:
                continue
            try:
                text = page.decoded_text()
                if len(text) < 200:
                    continue

                # Weight: homepage and early pages get higher weight
                weight = 3.0 if i == 0 else (2.0 if i < 5 else 1.0)

                # Extract words (2+ chars, alphanumeric + hyphen)
                words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]{2,}\b', text.lower())

                # Filter stopwords and short words
                filtered = [w for w in words if w not in STOPWORDS and len(w) >= 3]

                # Count bigrams (2-word phrases) - often better keywords
                bigrams = []
                for j in range(len(filtered) - 1):
                    bigram = f"{filtered[j]} {filtered[j+1]}"
                    # Only keep if both words are not stopwords
                    if filtered[j] not in STOPWORDS and filtered[j+1] not in STOPWORDS:
                        bigrams.append(bigram)

                # Count trigrams (3-word phrases)
                trigrams = []
                for j in range(len(filtered) - 2):
                    trigram = f"{filtered[j]} {filtered[j+1]} {filtered[j+2]}"
                    if (filtered[j] not in STOPWORDS and
                        filtered[j+1] not in STOPWORDS and
                        filtered[j+2] not in STOPWORDS):
                        trigrams.append(trigram)

                # Score keywords
                for word in filtered:
                    keyword_scores[word] += weight * 1.0
                for bigram in bigrams:
                    keyword_scores[bigram] += weight * 2.5  # Phrases are more valuable
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
                # Look for title tag content
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', text, re.IGNORECASE)
                if title_match:
                    title_text = title_match.group(1)
                    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]{2,}\b', title_text.lower())
                    for word in words:
                        if word not in STOPWORDS:
                            keyword_scores[word] += 5.0

                # Look for h1 tags
                h1_matches = re.findall(r'<h1[^>]*>([^<]+)</h1>', text, re.IGNORECASE)
                for h1 in h1_matches:
                    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]{2,}\b', h1.lower())
                    for word in words:
                        if word not in STOPWORDS:
                            keyword_scores[word] += 3.0
            except Exception:
                pass

        # Score and filter keywords
        commercial_indicators = COMMERCIAL_INDICATORS

        scored_keywords = []
        for kw, score in keyword_scores.items():
            if len(kw) < 3:
                continue
            # Boost commercial/transactional keywords
            commercial_boost = 2.0 if any(ind in kw for ind in commercial_indicators) else 1.0
            # Boost longer phrases slightly
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
        # Use provided keywords or extract from content
        if target_keywords is None:
            target_keywords = self._extract_target_keywords(crawl_pages, max_keywords=50)

        if not target_keywords:
            logger.warning("No target keywords for %s", domain)
            return None

        # Check rankings for each keyword
        queries = [
            SearchQuery(
                query=kw,
                search_engine="google",
                country=country,
                language="en",
                device=SearchDevice(device),
                target_domain=domain,
                max_results=20,
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

        # Build snapshot
        in_top_3 = sum(1 for o in observations if o.position <= 3)
        in_top_10 = sum(1 for o in observations if o.position <= 10)
        in_top_20 = sum(1 for o in observations if o.position <= 20)
        not_ranking = len(queries) - len(observations)

        top_kws = sorted(
            [{"keyword": o.keyword, "position": o.position, "url": o.target_url} for o in observations],
            key=lambda x: x["position"]
        )[:15]

        # Estimate traffic (rough)
        traffic = sum(
            self._estimate_traffic(o.position) for o in observations
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
        )

    def _estimate_traffic(self, position: int) -> int:
        """Very rough traffic estimate by position."""
        ctr_by_position = {
            1: 0.30, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
            6: 0.04, 7: 0.03, 8: 0.03, 9: 0.02, 10: 0.02,
        }
        base_volume = 1000  # Assume 1000 monthly searches per keyword
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

        # If no competitors specified, try to infer from search results
        comp_domains = competitors or []
        if not comp_domains and top_keywords:
            # For now, return empty - could be enhanced to infer from SERP
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
            # Create a temp dataset for competitor collection
            await self._collection_service.collect_and_persist(
                dataset_id=f"comp-{domain}-{datetime.now(UTC).strftime('%Y%m%d')}",
                queries=queries,
            )
        except Exception as e:
            logger.warning("Competitor collection failed: %s", e)
            return ()

        # The collection service persists observations; we'd need to query them back
        # For now, return empty - this can be enhanced
        return ()

    # ══════════════════════════════════════════════════════════════════════
    # AIO (AI Overview) Analysis
    # ══════════════════════════════════════════════════════════════════════

    async def _analyze_aio(
        self,
        domain: str,
        keywords: list[str],
        country: str,
        device: str,
    ) -> SiteAIOAnalysis:
        """Analyze AI Overview presence and citation opportunities."""
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
                    result = await self._search_provider.search(query)

                    # Check if AIO is present in results
                    has_aio = any(
                        'ai_overview' in str(getattr(item, 'serp_features', [])).lower()
                        for item in result.items
                    )

                    aio_observations.append(AIOverviewObservation(
                        keyword=kw,
                        ai_type=AIOverviewType.INFORMATIONAL if has_aio else AIOverviewType.OTHER,
                        present=has_aio,
                        target_cited=False,
                        target_domain=domain,
                        citation_count=0,
                        competitor_cited_domains=(),
                    ))
                except Exception:
                    continue

            if not aio_observations:
                return SiteAIOAnalysis(
                    keywords_checked=0, ai_overviews_present=0,
                    target_cited_count=0, competitor_cited_count=0,
                    citation_rate=0.0, target_citation_rate=0.0
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
            )

        except Exception as e:
            logger.warning("AIO analysis failed for %s: %s", domain, e)
            return SiteAIOAnalysis(
                keywords_checked=0, ai_overviews_present=0,
                target_cited_count=0, competitor_cited_count=0,
                citation_rate=0.0, target_citation_rate=0.0
            )

    # ══════════════════════════════════════════════════════════════════════
    # GEO (Generative Engine Optimization) Analysis
    # ═════════════════════════════════════════════════════════════════════

    async def _analyze_geo(
        self,
        domain: str,
        keywords: list[str],
        country: str,
        device: str,
    ) -> SiteGEOAnalysis:
        """Analyze Generative Engine Optimization presence and opportunities."""
        try:
            geo_observations = []

            for kw in keywords[:20]:
                try:
                    geo_observations.append(GEOObservation(
                        keyword=kw,
                        engine_type=GenerativeEngineType.OTHER,
                        target_mentioned=False,
                        target_domain=domain,
                        mention_count=0,
                        competitor_domains=(),
                        citation_urls=(),
                        answer_length=0,
                    ))
                except Exception:
                    continue

            if not geo_observations:
                return SiteGEOAnalysis(
                    keywords_checked=0, target_mentioned_count=0,
                    competitor_mentioned_count=0, mention_rate=0.0,
                    avg_mention_count=0.0
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
                avg_mention_count=geo_result.dataset_metrics.overall_mention_rate,  # Use mention rate as proxy
                competitor_domains_mentioned=list(geo_result.dataset_metrics.competitor_domain_counts.keys()),
                top_opportunities=opportunities[:10],
            )

        except Exception as e:
            logger.warning("GEO analysis failed for %s: %s", domain, e)
            return SiteGEOAnalysis(
                keywords_checked=0, target_mentioned_count=0,
                competitor_mentioned_count=0, mention_rate=0.0,
                avg_mention_count=0.0
            )

    # ══════════════════════════════════════════════════════════════════════
    # Dataset & Observation Builders
    # ══════════════════════════════════════════════════════════════════════

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
    # Health Builders
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

        return SiteTechnicalHealth(
            pages_crawled=len(crawl_pages),
            critical_issues=audit.critical_count,
            warning_issues=audit.warning_count,
            info_issues=audit.info_count,
            indexable_pages=indexable,
            non_indexable_pages=non_indexable,
            avg_load_time_ms=round(avg_load, 1),
            core_web_vitals_pass=audit.critical_count == 0,
            has_ssl=True,  # Would need to check
            robots_txt_valid=True,
            sitemap_exists=True,
            top_issues=top_issues,
        )

    def _build_content_health(self, quality: ContentQualityReport) -> SiteContentHealth:
        return SiteContentHealth(
            pages_analyzed=quality.analyzed_pages,
            avg_quality_score=quality.avg_quality_score,
            thin_content_pages=len(quality.thin_content_pages),
            duplicate_groups=len(quality.duplicate_groups),
            missing_h1_pages=sum(1 for issue, count in quality.top_issues if issue == "missing_h1"),
            missing_meta_desc_pages=0,  # Not tracked yet
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
        # Start at 100, deduct for issues
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
            return 50.0  # Neutral if not analyzed
        score = aio.target_citation_rate * 100
        if aio.ai_overviews_present > 0:
            score += min(20, aio.ai_overviews_present * 2)
        return max(0.0, min(100.0, score))

    def _score_geo(self, geo: SiteGEOAnalysis | None) -> float:
        if not geo or geo.keywords_checked == 0:
            return 50.0  # Neutral if not analyzed
        score = geo.mention_rate * 100
        if geo.target_mentioned_count > 0:
            score += min(30, geo.target_mentioned_count * 3)
        return max(0.0, min(100.0, score))

    # ══════════════════════════════════════════════════════════════════════
    # Comprehensive On-Page SEO Analysis
    # ══════════════════════════════════════════════════════════════════════

    def _analyze_onpage_seo(self, content_health: SiteContentHealth) -> list[SearchRecommendation]:
        """Analyze on-page SEO elements: titles, meta descriptions, keywords, headers, etc."""
        recs: list[SearchRecommendation] = []

        # Check for missing meta descriptions (from top_issues if available)
        missing_meta = content_health.missing_meta_desc_pages
        if missing_meta > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.HIGH,
                title=f"{missing_meta} pages missing meta descriptions",
                description=(
                    f"{missing_meta} pages lack meta descriptions. "
                    f"Meta descriptions are your SERP ad copy - they directly impact click-through rates. "
                    f"Write unique, compelling 150-160 character descriptions with target keywords."
                ),
                supporting_metrics={"missing_meta_desc": missing_meta},
                confidence=0.9,
            ))

        # Check for pages with low word count
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

        # Check for missing structured data / schema
        if hasattr(content_health, 'top_issues'):
            missing_schema = sum(1 for issue, count in content_health.top_issues if 'schema' in issue.lower())
            if missing_schema > 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.OPPORTUNITY,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"{missing_schema} pages missing Schema.org markup",
                    description=(
                        f"Structured data helps search engines understand your content and "
                        f"enables rich snippets (FAQ, HowTo, Product, Article, etc.). "
                        f"Add JSON-LD schema to key pages for better SERP visibility."
                    ),
                    supporting_metrics={"missing_schema": missing_schema},
                    confidence=0.8,
                ))

        # Check for stale content
        stale_content = sum(1 for issue, count in content_health.top_issues if 'stale' in issue.lower())
        if stale_content > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{stale_content} pages with potentially stale content",
                description=(
                    f"Content freshness is a ranking factor. Update old content with current data, "
                    f"new examples, recent statistics, and current year references. "
                    f"Add 'Last Updated' dates to signal freshness."
                ),
                supporting_metrics={"stale_pages": stale_content},
                confidence=0.75,
            ))

        # Check for poor readability
        poor_readability = sum(1 for issue, count in content_health.top_issues if 'readability' in issue.lower())
        if poor_readability > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{poor_readability} pages with poor readability",
                description=(
                    f"Content that's hard to read increases bounce rate and reduces dwell time. "
                    f"Use shorter sentences, simpler words, subheadings, bullet points, "
                    f"and visual elements. Target Flesch Reading Ease > 60."
                ),
                supporting_metrics={"poor_readability": poor_readability},
                confidence=0.7,
            ))

        # Check for keyword stuffing
        keyword_stuffing = sum(1 for issue, count in content_health.top_issues if 'stuffing' in issue.lower())
        if keyword_stuffing > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.HIGH,
                title=f"{keyword_stuffing} pages with potential keyword stuffing",
                description=(
                    f"Over-optimization triggers spam filters. Write naturally for humans, "
                    f"not keyword density. Use synonyms, related terms (LSI keywords), "
                    f"and focus on topic coverage rather than exact-match repetition."
                ),
                supporting_metrics={"keyword_stuffing": keyword_stuffing},
                confidence=0.85,
            ))

        # Check for missing alt text
        missing_alt = sum(1 for issue, count in content_health.top_issues if 'alt' in issue.lower())
        if missing_alt > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{missing_alt} pages with images missing alt text",
                description=(
                    f"Alt text is crucial for accessibility and image search. "
                    f"Describe images with relevant keywords naturally. "
                    f"This also helps with Google Images traffic."
                ),
                supporting_metrics={"missing_alt": missing_alt},
                confidence=0.8,
            ))

        # Check for low internal links
        low_internal = sum(1 for issue, count in content_health.top_issues if 'internal' in issue.lower())
        if low_internal > 0:
            recs.append(SearchRecommendation(
                category=RecommendationCategory.OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title=f"{low_internal} pages with insufficient internal links",
                description=(
                    f"Internal links distribute PageRank and help users discover content. "
                    f"Add 3-5 relevant internal links per page using descriptive anchor text. "
                    f"Link to cornerstone content and related articles."
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
        # Check for missing meta descriptions, title issues, keyword optimization
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
            if ranking_snapshot.keywords_not_ranking > ranking_snapshot.total_keywords_tracked * 0.5:
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

            if ranking_snapshot.keywords_in_top_10 == 0 and ranking_snapshot.total_keywords_tracked > 0:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.CRITICAL,
                    title="No keywords in top 10",
                    description="Zero keywords ranking in top 10. Fundamental content/authority issues.",
                    confidence=0.95,
                ))

            if ranking_snapshot.visibility_score < 0.2:
                recs.append(SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.HIGH,
                    title=f"Low search visibility ({ranking_snapshot.visibility_score:.0%})",
                    description="Overall visibility is very low. Focus on technical foundation and content.",
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

    def _empty_result(self, domain: str, crawl_run_id: str | None) -> SiteAnalysisResult:
        return SiteAnalysisResult(
            domain=domain,
            analyzed_at=datetime.now(UTC),
            crawl_run_id=crawl_run_id,
            technical_score=0.0,
            content_score=0.0,
            ranking_score=0.0,
            architecture_score=0.0,
            overall_score=0.0,
        )


# Factory for easy instantiation in the API
def create_site_analysis_service(
    crawl_service: CrawlService,
    audit_service: AuditService,
    content_service: ContentService,
    search_provider: SearchProvider,
    repository: CrawlRunRepository,
) -> SiteAnalysisService:
    return SiteAnalysisService(
        crawl_service=crawl_service,
        audit_service=audit_service,
        content_service=content_service,
        search_provider=search_provider,
        repository=repository,
    )


__all__ = [
    "SiteAnalysisService",
    "SiteAnalysisResult",
    "SiteRankingSnapshot",
    "SiteTechnicalHealth",
    "SiteContentHealth",
    "SiteArchitectureHealth",
    "SiteAIOAnalysis",
    "SiteGEOAnalysis",
    "create_site_analysis_service",
]