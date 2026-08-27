"""Unified Search Intelligence Service (Phase 6N-H).

Orchestrates all search intelligence capabilities into a single, actionable
intelligence result.  Combines:
- Ranking intelligence (keyword metrics, visibility)
- Competitor intelligence (gaps, outranking)
- SERP feature intelligence (feature ownership, opportunities)
- Cannibalization detection
- Ranking volatility analysis
- Search opportunity identification
- AIO (AI Overview) visibility
- GEO (Generative Engine Optimization) visibility

Produces deterministic, prioritised recommendations without fabricating data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from sie.domain.engines.search_analytics import analyze_search_dataset
from sie.domain.models.search import CompetitorRanking, RankingObservation, SearchDataset
from sie.domain.models.search_aio import AIOverviewResult
from sie.domain.models.search_analytics import SearchAnalyticsResult
from sie.domain.models.search_geo import GEOResult
from sie.domain.services.cannibalization import (
    CannibalizationDetector,
    CannibalizationFinding,
)
from sie.domain.services.ranking_volatility import (
    RankingVolatilityMetrics,
    RankingVolatilityService,
)
from sie.domain.services.search_opportunity import SearchOpportunityResult, SearchOpportunityService
from sie.domain.services.search_trends import calculate_aio_trend, calculate_geo_trend


class RecommendationPriority(StrEnum):
    """Priority levels for search intelligence recommendations."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationCategory(StrEnum):
    """Categories of search intelligence recommendations."""

    RANKING = "ranking"
    COMPETITOR = "competitor"
    SERP_FEATURE = "serp_feature"
    CANNIBALIZATION = "cannibalization"
    VOLATILITY = "volatility"
    OPPORTUNITY = "opportunity"
    AIO = "aio"
    GEO = "geo"


@dataclass(frozen=True, slots=True)
class SearchRecommendation:
    """A single actionable recommendation from the search intelligence layer."""

    category: RecommendationCategory
    priority: RecommendationPriority
    title: str
    description: str
    affected_keywords: tuple[str, ...] = ()
    affected_urls: tuple[str, ...] = ()
    supporting_metrics: dict[str, object] = field(default_factory=dict)
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class SearchIntelligenceSummary:
    """High-level summary statistics for the search intelligence result."""

    total_keywords: int = 0
    keywords_ranking: int = 0
    keywords_not_ranking: int = 0
    visibility_score: float = 0.0
    cannibalization_count: int = 0
    volatile_keyword_count: int = 0
    opportunity_count: int = 0
    serp_feature_opportunity_count: int = 0
    competitor_gap_count: int = 0
    weak_ranking_count: int = 0
    content_gap_count: int = 0


@dataclass(frozen=True, slots=True)
class SearchIntelligenceResult:
    """Complete unified search intelligence result.

    Aggregates all search intelligence capabilities into a single,
    actionable result with prioritised recommendations.
    """

    dataset_id: str
    summary: SearchIntelligenceSummary
    recommendations: tuple[SearchRecommendation, ...]
    analytics: SearchAnalyticsResult
    cannibalization_findings: tuple[CannibalizationFinding, ...]
    volatility_metrics: tuple[RankingVolatilityMetrics, ...]
    opportunity_result: SearchOpportunityResult | None


class SearchIntelligenceService:
    """Unified search intelligence service.

    Orchestrates all search intelligence capabilities and produces
    prioritised, actionable recommendations.
    """

    def __init__(self) -> None:
        self._cannibalization_detector = CannibalizationDetector()
        self._volatility_service = RankingVolatilityService()
        self._opportunity_service = SearchOpportunityService()

    def analyze(
        self,
        dataset: SearchDataset,
        observations: tuple[RankingObservation, ...],
        competitor_rankings: tuple[CompetitorRanking, ...],
        target_domain: str = "",
        aio_result: AIOverviewResult | None = None,
        geo_result: GEOResult | None = None,
    ) -> SearchIntelligenceResult:
        """Run full search intelligence analysis and produce recommendations.

        Deterministic: same inputs always produce the same output.
        """
        # 1. Core analytics
        analytics = analyze_search_dataset(dataset, observations, competitor_rankings)

        # 2. Cannibalization detection
        cannibalization_findings = self._cannibalization_detector.detect_cannibalization(
            observations
        )

        # 3. Ranking volatility
        volatility_metrics = self._volatility_service.calculate_volatility_by_keyword(observations)

        # 4. Search opportunities
        opportunity_result = self._opportunity_service.calculate_opportunities(
            dataset, analytics, competitor_rankings, target_domain=target_domain
        )

        # 5. Build recommendations
        recommendations = self._build_recommendations(
            analytics,
            cannibalization_findings,
            volatility_metrics,
            opportunity_result,
            aio_result=aio_result,
            geo_result=geo_result,
        )

        # 6. Build summary
        summary = self._build_summary(
            analytics,
            cannibalization_findings,
            volatility_metrics,
            opportunity_result,
        )

        return SearchIntelligenceResult(
            dataset_id=dataset.dataset_id,
            summary=summary,
            recommendations=tuple(recommendations),
            analytics=analytics,
            cannibalization_findings=cannibalization_findings,
            volatility_metrics=volatility_metrics,
            opportunity_result=opportunity_result,
        )

    def _build_summary(
        self,
        analytics: SearchAnalyticsResult,
        cannibalization: tuple[CannibalizationFinding, ...],
        volatility_metrics: tuple[RankingVolatilityMetrics, ...],
        opportunities: SearchOpportunityResult | None,
    ) -> SearchIntelligenceSummary:
        """Build high-level summary from all intelligence components."""
        m = analytics.dataset_metrics
        opp_count = 0
        comp_gap_count = 0
        weak_count = 0
        content_gap_count = 0

        if opportunities:
            opp_count = opportunities.total_opportunities
            comp_gap_count = len(opportunities.competitor_gaps)
            weak_count = len(opportunities.weak_ranking_opportunities)
            content_gap_count = len(opportunities.content_gaps)

        volatile_count = sum(1 for vm in volatility_metrics if vm.volatility >= 0.3)

        return SearchIntelligenceSummary(
            total_keywords=m.total_keywords,
            keywords_ranking=m.keywords_with_rankings,
            keywords_not_ranking=m.keywords_not_ranking,
            visibility_score=m.visibility_score,
            cannibalization_count=len(cannibalization),
            volatile_keyword_count=volatile_count,
            opportunity_count=opp_count,
            serp_feature_opportunity_count=(
                m.featured_snippet_occurrences + m.people_also_ask_occurrences
            ),
            competitor_gap_count=comp_gap_count,
            weak_ranking_count=weak_count,
            content_gap_count=content_gap_count,
        )

    def _build_recommendations(
        self,
        analytics: SearchAnalyticsResult,
        cannibalization: tuple[CannibalizationFinding, ...],
        volatility_metrics: tuple[RankingVolatilityMetrics, ...],
        opportunities: SearchOpportunityResult | None,
        aio_result: AIOverviewResult | None = None,
        geo_result: GEOResult | None = None,
    ) -> list[SearchRecommendation]:
        """Build prioritised recommendations from all intelligence components."""
        recs: list[SearchRecommendation] = []

        # ── Cannibalization recommendations ──
        for finding in cannibalization:
            if finding.severity == "extreme":
                priority = RecommendationPriority.CRITICAL
            elif finding.severity == "high":
                priority = RecommendationPriority.HIGH
            elif finding.severity == "medium":
                priority = RecommendationPriority.MEDIUM
            else:
                priority = RecommendationPriority.LOW

            recs.append(
                SearchRecommendation(
                    category=RecommendationCategory.CANNIBALIZATION,
                    priority=priority,
                    title=f"Cannibalization: {finding.keyword}",
                    description=(
                        f"Multiple URLs compete for '{finding.keyword}': "
                        f"{len(finding.competing_urls)} URLs. "
                        f"Consider canonical tags, content consolidation, "
                        f"or internal linking adjustments."
                    ),
                    affected_keywords=(finding.keyword,),
                    affected_urls=finding.competing_urls,
                    supporting_metrics={
                        "severity": finding.severity,
                        "competing_url_count": len(finding.competing_urls),
                    },
                    confidence=0.9,
                )
            )

        # ── Volatility recommendations ──
        for vm in volatility_metrics:
            if vm.volatility >= 0.3:
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.VOLATILITY,
                        priority=RecommendationPriority.HIGH,
                        title=f"Volatile ranking: {vm.keyword}",
                        description=(
                            f"Keyword '{vm.keyword}' shows high ranking "
                            f"volatility (score: {vm.volatility:.2f}, "
                            f"severity: {vm.severity}). "
                            f"Review content stability and competitor "
                            f"activity for this keyword."
                        ),
                        affected_keywords=(vm.keyword,),
                        supporting_metrics={
                            "volatility_score": vm.volatility,
                            "severity": vm.severity,
                        },
                        confidence=0.8,
                    )
                )

        # ── Opportunity recommendations ──
        if opportunities:
            for gap in opportunities.competitor_gaps:
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.OPPORTUNITY,
                        priority=RecommendationPriority.HIGH,
                        title=f"Competitor gap: {gap.keyword}",
                        description=(
                            f"Competitors rank for '{gap.keyword}' but "
                            f"target does not. "
                            f"{gap.estimated_improvement or ''}"
                        ),
                        affected_keywords=(gap.keyword,),
                        supporting_metrics={
                            "competitor_domain": gap.competitor_domain,
                            "severity": gap.severity,
                            "confidence": gap.confidence_score,
                        },
                        confidence=gap.confidence_score,
                    )
                )

            for weak in opportunities.weak_ranking_opportunities:
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.OPPORTUNITY,
                        priority=RecommendationPriority.MEDIUM,
                        title=f"Weak ranking: {weak.keyword}",
                        description=(
                            f"Target ranks at position {weak.target_position} "
                            f"for '{weak.keyword}' but could improve. "
                            f"{weak.estimated_improvement or ''}"
                        ),
                        affected_keywords=(weak.keyword,),
                        supporting_metrics={
                            "target_position": weak.target_position,
                            "severity": weak.severity,
                            "confidence": weak.confidence_score,
                        },
                        confidence=weak.confidence_score,
                    )
                )

            for gap in opportunities.content_gaps:
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.OPPORTUNITY,
                        priority=RecommendationPriority.MEDIUM,
                        title=f"Content gap: {gap.keyword}",
                        description=(
                            f"No content exists for '{gap.keyword}' but "
                            f"{gap.competitor_count} competitors rank. "
                            f"Avg competitor position: "
                            f"{gap.average_competitor_position:.1f}."
                        ),
                        affected_keywords=(gap.keyword,),
                        supporting_metrics={
                            "competitor_count": gap.competitor_count,
                            "avg_position": gap.average_competitor_position,
                            "primary_competitor": gap.primary_competitor,
                        },
                        confidence=gap.confidence_score,
                    )
                )

        # ── SERP feature recommendations ──
        dm = analytics.dataset_metrics
        if dm.featured_snippet_occurrences > 0:
            unowned_fs = dm.featured_snippet_occurrences - dm.featured_snippet_owned_by_target
            if unowned_fs > 0:
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.SERP_FEATURE,
                        priority=RecommendationPriority.MEDIUM,
                        title="Featured snippet opportunity",
                        description=(
                            f"{unowned_fs} featured snippet(s) appear for "
                            f"tracked keywords but target does not own them. "
                            f"Consider optimising content for snippet "
                            f"capture."
                        ),
                        supporting_metrics={
                            "total_featured_snippets": (dm.featured_snippet_occurrences),
                            "owned": dm.featured_snippet_owned_by_target,
                            "unowned": unowned_fs,
                        },
                        confidence=0.7,
                    )
                )

        if dm.people_also_ask_occurrences > 0:
            unowned_paa = dm.people_also_ask_occurrences - dm.people_also_ask_owned_by_target
            if unowned_paa > 0:
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.SERP_FEATURE,
                        priority=RecommendationPriority.LOW,
                        title="People Also Ask opportunity",
                        description=(
                            f"{unowned_paa} PAA box(es) appear for tracked "
                            f"keywords but target does not own them. "
                            f"Consider FAQ content optimisation."
                        ),
                        supporting_metrics={
                            "total_paa": dm.people_also_ask_occurrences,
                            "owned": dm.people_also_ask_owned_by_target,
                            "unowned": unowned_paa,
                        },
                        confidence=0.6,
                    )
                )

        # ── Ranking recommendations ──
        if dm.keywords_not_ranking > 0:
            recs.append(
                SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.HIGH,
                    title=f"{dm.keywords_not_ranking} keywords not ranking",
                    description=(
                        f"{dm.keywords_not_ranking} tracked keywords have "
                        f"no current ranking. Review content and technical "
                        f"SEO for these keywords."
                    ),
                    supporting_metrics={
                        "keywords_not_ranking": dm.keywords_not_ranking,
                        "total_keywords": dm.total_keywords,
                    },
                    confidence=0.9,
                )
            )

        if dm.visibility_score < 0.3 and dm.total_keywords > 0:
            recs.append(
                SearchRecommendation(
                    category=RecommendationCategory.RANKING,
                    priority=RecommendationPriority.CRITICAL,
                    title="Low visibility score",
                    description=(
                        f"Visibility score is {dm.visibility_score:.2f} "
                        f"(below 0.3 threshold). Most tracked keywords "
                        f"rank poorly or not at all."
                    ),
                    supporting_metrics={
                        "visibility_score": dm.visibility_score,
                    },
                    confidence=0.95,
                )
            )

        # ── AIO recommendations ──
        if aio_result:
            self._add_aio_recommendations(recs, aio_result)

        # ── GEO recommendations ──
        if geo_result:
            self._add_geo_recommendations(recs, geo_result)

        # ── Cross-engine recommendations ──
        if aio_result and geo_result:
            self._add_cross_engine_recommendations(recs, aio_result, geo_result)

        # Sort by priority (critical first) then confidence
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        recs.sort(key=lambda r: (priority_order[r.priority], -r.confidence))

        return recs

    def _add_aio_recommendations(
        self,
        recs: list[SearchRecommendation],
        aio_result: AIOverviewResult,
    ) -> None:
        """Add AIO-specific recommendations based on observations."""
        dm = aio_result.dataset_metrics

        # AIO presence but target not cited
        if dm.keywords_with_ai_overview > 0 and dm.keywords_target_cited == 0:
            competitors = (
                ", ".join(dm.competitor_cited_domains)
                if dm.competitor_cited_domains
                else "none"
            )
            recs.append(
                SearchRecommendation(
                    category=RecommendationCategory.AIO,
                    priority=RecommendationPriority.HIGH,
                    title="AI Overviews present but site not cited",
                    description=(
                        f"AI Overviews appear for {dm.keywords_with_ai_overview} target keywords "
                        f"but the target domain is not cited in any. "
                        f"Competitors cited: {competitors}. "
                        f"Create authoritative content that directly answers these queries."
                    ),
                    supporting_metrics={
                        "keywords_with_ai_overview": dm.keywords_with_ai_overview,
                        "target_cited_count": dm.keywords_target_cited,
                        "competitor_cited_domains": list(dm.competitor_cited_domains),
                    },
                    confidence=0.85,
                )
            )

        # Low citation rate despite AIO presence
        elif dm.keywords_with_ai_overview > 0 and dm.target_citation_rate < 0.3:
            recs.append(
                SearchRecommendation(
                    category=RecommendationCategory.AIO,
                    priority=RecommendationPriority.MEDIUM,
                    title="Low AIO citation rate",
                    description=(
                        f"AI Overviews appear for {dm.keywords_with_ai_overview} keywords "
                        f"but target is only cited in {dm.target_citation_rate:.0%} of them. "
                        f"Competitors are cited more frequently."
                    ),
                    supporting_metrics={
                        "target_citation_rate": dm.target_citation_rate,
                        "competitor_cited_domains": list(dm.competitor_cited_domains),
                    },
                    confidence=0.75,
                )
            )

        # Competitors cited in AIO
        if dm.competitor_cited_domains:
            # competitor_cited_domains is a tuple of unique domain names cited across observations.
            # No per-competitor citation count is available at dataset level, so we report all.
            cited_comps = list(dm.competitor_cited_domains)
            recs.append(
                SearchRecommendation(
                    category=RecommendationCategory.AIO,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"{len(cited_comps)} competitor(s) cited in AI Overviews",
                    description=(
                        f"Competitors cited in AI Overviews: {', '.join(cited_comps)}. "
                        f"Analyze their content structure and authority signals."
                    ),
                    supporting_metrics={
                        "competitor_count": len(cited_comps),
                        "all_cited_competitors": cited_comps,
                    },
                    confidence=0.7,
                )
            )

    def _add_geo_recommendations(
        self,
        recs: list[SearchRecommendation],
        geo_result: GEOResult,
    ) -> None:
        """Add GEO-specific recommendations based on observations."""
        dm = geo_result.dataset_metrics
        competitor_counts = dm.competitor_domain_counts
        total_competitor_mentions = sum(competitor_counts.values()) if competitor_counts else 0

        # Target not mentioned but competitors are
        if dm.keywords_target_mentioned == 0 and total_competitor_mentions > 0:
            top_comps = ", ".join(list(competitor_counts.keys())[:3])
            recs.append(
                SearchRecommendation(
                    category=RecommendationCategory.GEO,
                    priority=RecommendationPriority.HIGH,
                    title="Target not mentioned in generative engines",
                    description=(
                        f"Target brand not mentioned in any of {dm.total_keywords} "
                        f"queries across generative engines, while competitors mentioned "
                        f"{total_competitor_mentions} times. "
                        f"Top competitors: {top_comps}."
                    ),
                    supporting_metrics={
                        "target_mentioned_count": dm.keywords_target_mentioned,
                        "competitor_mentioned_count": total_competitor_mentions,
                        "top_competitors": list(competitor_counts.keys())[:5],
                    },
                    confidence=0.85,
                )
            )

        # Target mentioned but low mention rate
        elif dm.overall_mention_rate > 0 and dm.overall_mention_rate < 0.3:
            recs.append(
                SearchRecommendation(
                    category=RecommendationCategory.GEO,
                    priority=RecommendationPriority.MEDIUM,
                    title="Low GEO mention rate",
                    description=(
                        f"Target mentioned in only {dm.overall_mention_rate:.0%} "
                        f"of queries. Competitors mentioned more frequently."
                    ),
                    supporting_metrics={
                        "mention_rate": dm.overall_mention_rate,
                        "competitor_mention_rate": total_competitor_mentions
                        / max(dm.total_keywords, 1),
                    },
                    confidence=0.7,
                )
            )

        # Competitors heavily mentioned
        if dm.competitor_domain_counts:
            top_comp = max(
                dm.competitor_domain_counts.items(),
                key=lambda x: x[1],
                default=(None, 0),
            )
            if top_comp[0]:
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.GEO,
                        priority=RecommendationPriority.MEDIUM,
                        title=f"Competitor {top_comp[0]} dominates GEO mentions",
                        description=(
                            f"Competitor {top_comp[0]} mentioned {top_comp[1]} times "
                            f"across {dm.total_keywords} queries. "
                            f"Analyze their content strategy for GEO visibility."
                        ),
                        supporting_metrics={
                            "competitor": top_comp[0],
                            "mention_count": top_comp[1],
                        },
                        confidence=0.7,
                    )
                )

    def _add_cross_engine_recommendations(
        self,
        recs: list[SearchRecommendation],
        aio_result: AIOverviewResult,
        geo_result: GEOResult,
    ) -> None:
        """Add cross-engine recommendations combining AIO and GEO insights."""
        aio_dm = aio_result.dataset_metrics
        geo_dm = geo_result.dataset_metrics

        # Cross-engine: AIO citation gap + GEO mention gap for same queries
        if aio_result.dataset_id and geo_result.dataset_id:
            aio_gap_keywords = {
                km.keyword
                for km in aio_result.keyword_metrics
                if km.ai_overview_present_count > 0 and km.target_cited_count == 0
            }
            geo_gap_keywords = {
                km.keyword
                for km in geo_result.keyword_metrics
                if km.target_mentioned_count == 0 and km.competitor_mentioned_count > 0
            }

            cross_gap = aio_gap_keywords & geo_gap_keywords
            if cross_gap:
                priority_queries = ", ".join(list(cross_gap)[:5])
                desc = (
                    f"{len(cross_gap)} queries have AI Overviews without target citation "
                    f"AND target not mentioned in generative engines while competitors appear. "
                    f"Priority queries: {priority_queries}"
                )
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.OPPORTUNITY,
                        priority=RecommendationPriority.HIGH,
                        title="Cross-engine visibility gap",
                        description=desc,
                        affected_keywords=tuple(cross_gap),
                        supporting_metrics={
                            "cross_gap_count": len(cross_gap),
                            "aio_gap_count": len(aio_gap_keywords),
                            "geo_gap_count": len(geo_gap_keywords),
                        },
                        confidence=0.85,
                    )
                )

        # AIO citation rate + GEO mention rate correlation
        aio_kw_count = aio_dm.keywords_with_ai_overview
        geo_kw_count = geo_dm.keywords_target_mentioned
        if aio_kw_count > 0 and geo_kw_count > 0:
            aio_citation_rate = aio_dm.target_citation_rate
            geo_mention_rate = geo_dm.overall_mention_rate

            if aio_citation_rate < 0.3 and geo_mention_rate < 0.3:
                recs.append(
                    SearchRecommendation(
                        category=RecommendationCategory.OPPORTUNITY,
                        priority=RecommendationPriority.MEDIUM,
                        title="Low visibility across both AIO and GEO",
                        description=(
                            f"Low AIO citation rate ({aio_citation_rate:.0%}) "
                            f"and low GEO mention rate ({geo_mention_rate:.0%}). "
                            f"Content strategy should address both AI Overview citations "
                            f"and generative engine visibility."
                        ),
                        supporting_metrics={
                            "aio_citation_rate": aio_citation_rate,
                            "geo_mention_rate": geo_mention_rate,
                        },
                        confidence=0.7,
                    )
                )


__all__ = [
    "RecommendationCategory",
    "RecommendationPriority",
    "SearchIntelligenceResult",
    "SearchIntelligenceService",
    "SearchIntelligenceSummary",
    "SearchRecommendation",
    "calculate_aio_trend",
    "calculate_geo_trend",
]
