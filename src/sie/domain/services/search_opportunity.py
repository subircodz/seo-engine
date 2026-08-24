"""Search Opportunity Intelligence (Phase 6N-E).

Implements actionable SEO opportunity scoring using available ranking/competitor evidence.

Builds opportunity scoring around available ranking/competitor evidence, identifying:
- Keywords where competitors rank but target site does not (competitor gaps)
- Weak-ranking opportunities (target present but underperforming)
- Deterministic prioritization without fabricated data
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering

from sie.domain.models.search import (
    CompetitorRanking,
    SearchDataset,
)
from sie.domain.models.search_analytics import SearchAnalyticsResult


@dataclass(frozen=True, slots=True)
class SearchOpportunity:
    """Actionable SEO opportunity derived from available evidence.

    Represents a specific keyword/URL combination with a ranking improvement
    potential, based on measurable data from competitor rankings or target
    ranking performance.
    """

    keyword: str
    target_url: str
    target_domain: str
    competitor_domain: str
    target_position: int | None = None
    competitor_position: int | None = None
    opportunity_type: str = "competitor_gap"
    severity: str = "medium"
    confidence_score: float = 0.5
    estimated_improvement: str | None = None

    def __post_init__(self) -> None:
        if self.opportunity_type not in ("competitor_gap", "weak_ranking"):
            raise ValueError(
                f"opportunity_type must be 'competitor_gap' or "
                f"'weak_ranking', got {self.opportunity_type}"
            )

        if self.severity not in ("low", "medium", "high", "critical"):
            raise ValueError(
                f"severity must be one of 'low', 'medium', 'high', 'critical', got {self.severity}"
            )

        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(f"confidence_score must be in [0.0, 1.0], got {self.confidence_score}")

        # competitor_gap requires competitor_position to define the gap;
        # when target_position is set the gap is relative to a competitor.
        if (
            self.opportunity_type == "competitor_gap"
            and self.target_position is not None
            and self.competitor_position is None
        ):
            raise ValueError(
                "competitor_gap opportunity requires competitor_position "
                "when target_position is provided"
            )

        # weak_ranking means the target is ranking on its own; a specific
        # competitor position is not part of this opportunity type.
        if self.opportunity_type == "weak_ranking" and self.competitor_position is not None:
            raise ValueError("weak_ranking opportunity must not have competitor_position")

    @property
    def is_competitor_gap(self) -> bool:
        return self.opportunity_type == "competitor_gap"

    @property
    def is_weak_ranking(self) -> bool:
        return self.opportunity_type == "weak_ranking"


@total_ordering
@dataclass(frozen=True, slots=True)
class ContentGapOpportunity:
    """Content gap identified through competitor analysis.

    Represents a keyword where competitors rank with content, but the target
    site is absent entirely, indicating a content opportunity.
    """

    keyword: str
    target_domain: str
    competitor_domains: tuple[str, ...]
    competitor_urls: tuple[str, ...]
    competitor_positions: tuple[int, ...]
    average_competitor_position: float
    primary_competitor: str
    confidence_score: float
    content_description_hint: str | None = None

    def __post_init__(self) -> None:
        if not self.competitor_domains:
            raise ValueError("competitor_domains must not be empty")

        if len(self.competitor_domains) != len(self.competitor_urls) or len(
            self.competitor_urls
        ) != len(self.competitor_positions):
            raise ValueError(
                "competitor_domains, competitor_urls, and "
                "competitor_positions must have same length"
            )

        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(f"confidence_score must be in [0.0, 1.0], got {self.confidence_score}")

    @property
    def competitor_count(self) -> int:
        return len(self.competitor_domains)

    @property
    def average_position_rank(self) -> str:
        avg = self.average_competitor_position
        if avg <= 3:
            return "top_3"
        elif avg < 10:
            return "top_10"
        else:
            return "outside_top_20"

    def __lt__(self, other: ContentGapOpportunity) -> bool:
        return self.average_competitor_position < other.average_competitor_position


@dataclass(frozen=True, slots=True)
class SearchOpportunityResult:
    """Complete search opportunity analysis.

    Aggregates opportunities from multiple data sources into a single
    actionable result.
    """

    dataset_id: str
    competitor_gaps: tuple[SearchOpportunity, ...]
    weak_ranking_opportunities: tuple[SearchOpportunity, ...]
    content_gaps: tuple[ContentGapOpportunity, ...]
    total_opportunities: int

    @property
    def sorted_by_priority(self) -> SearchOpportunityResult:
        """Return result sorted by opportunity priority (severity + confidence).

        Sorting is descending: critical severity first, then by highest
        confidence score.
        """
        opps = list(self.competitor_gaps) + list(self.weak_ranking_opportunities)
        sorted_opps = tuple(
            sorted(
                opps,
                key=lambda o: (
                    -{"critical": 4, "high": 3, "medium": 2, "low": 1}[o.severity],
                    -o.confidence_score,
                ),
            )
        )
        return SearchOpportunityResult(
            dataset_id=self.dataset_id,
            competitor_gaps=tuple(o for o in sorted_opps if o.is_competitor_gap),
            weak_ranking_opportunities=tuple(o for o in sorted_opps if o.is_weak_ranking),
            content_gaps=self.content_gaps,
            total_opportunities=self.total_opportunities,
        )


class SearchOpportunityService:
    """Domain service for calculating SEO search opportunities.

    This service implements Phase 6N-E opportunity analysis, providing
    actionable insights for SEO optimization based on measurable ranking
    and competitor data.

    Key principles:
    - Uses only available data, no fabricated metrics
    - Identifies clear opportunity types (gaps, weak rankings)
    - Provides deterministic, reproducible results
    - Delivers actionable intelligence for SEO teams
    """

    def calculate_opportunities(
        self,
        dataset: SearchDataset,
        analytics_result: SearchAnalyticsResult,
        competitor_rankings: tuple[CompetitorRanking, ...],
    ) -> SearchOpportunityResult:
        """Calculate all SEO opportunities for the dataset.

        Combines competitor gap analysis, weak ranking detection, and content
        gap identification into a single actionable result.
        """
        # Extract target domain from dataset metadata
        target_domain = self._derive_target_domain(analytics_result)

        # Calculate all opportunity types
        competitor_gaps = self._calculate_competitor_gaps(
            analytics_result, competitor_rankings, target_domain
        )
        weak_rankings = self._calculate_weak_rankings(
            analytics_result, competitor_rankings, target_domain
        )
        content_gaps = self._calculate_content_gaps(analytics_result, competitor_rankings)

        # Aggregate all opportunities
        all_opps = list(competitor_gaps) + list(weak_rankings)
        total_opps = len(all_opps) + len(content_gaps)

        return SearchOpportunityResult(
            dataset_id=dataset.dataset_id,
            competitor_gaps=competitor_gaps,
            weak_ranking_opportunities=weak_rankings,
            content_gaps=content_gaps,
            total_opportunities=total_opps,
        )

    def _derive_target_domain(self, analytics_result: SearchAnalyticsResult) -> str:
        """Derive target domain from analytics metadata."""
        # Placeholder — actual implementation would depend on dataset
        return "example.com"

    # ------------------------------------------------------------------
    # Competitor gaps
    # ------------------------------------------------------------------

    def _calculate_competitor_gaps(
        self,
        analytics_result: SearchAnalyticsResult,
        competitor_rankings: tuple[CompetitorRanking, ...],
        target_domain: str,
    ) -> tuple[SearchOpportunity, ...]:
        """Calculate opportunities where competitors rank but target does not.

        A competitor gap exists when:
        1. The keyword appears in the target's keyword_metrics
        2. The target is NOT currently ranking (latest_position is None)
        3. The target has at most one observation (not actively tracked)
        4. Multiple competitors rank for that keyword
        """
        opportunities: list[SearchOpportunity] = []

        # Map keyword → latest_position from analytics
        our_keyword_positions: dict[str, int | None] = {
            km.keyword: km.latest_position for km in analytics_result.keyword_metrics
        }

        # Build an observation-count lookup
        obs_count_by_kw: dict[str, int] = {
            km.keyword: km.observation_count for km in analytics_result.keyword_metrics
        }

        # Group competitor rankings by keyword
        competitors_by_keyword = self._group_by_keyword(competitor_rankings)

        for keyword, competitors in competitors_by_keyword.items():
            # Must be tracked by the target
            if keyword not in our_keyword_positions:
                continue

            our_position = our_keyword_positions[keyword]

            # Target is currently ranking → not a gap
            if our_position is not None:
                continue

            # If target has multiple observations it is actively tracked;
            # only keywords with ≤1 observation qualify as gaps.
            if obs_count_by_kw.get(keyword, 0) > 1:
                continue

            # Need at least 2 distinct competitor domains
            distinct_domains = {c.competitor_domain for c in competitors}
            if len(distinct_domains) < 2:
                continue

            avg_comp_pos = sum(c.position for c in competitors) / len(competitors)

            confidence = min(len(competitors) / 10.0, 1.0)

            if avg_comp_pos <= 3:
                severity = "critical"
            elif avg_comp_pos <= 10:
                severity = "high"
            elif avg_comp_pos <= 20:
                severity = "medium"
            else:
                severity = "low"

            primary_comp = min(competitors, key=lambda c: c.position)

            opportunities.append(
                SearchOpportunity(
                    keyword=keyword,
                    target_url="",
                    target_domain=target_domain,
                    competitor_domain=primary_comp.competitor_domain,
                    target_position=our_position,
                    competitor_position=primary_comp.position,
                    opportunity_type="competitor_gap",
                    severity=severity,
                    confidence_score=confidence,
                    estimated_improvement=(
                        f"Target site is not ranking for keyword "
                        f"'{keyword}'. Competitors average position: "
                        f"{avg_comp_pos:.1f}"
                    ),
                )
            )

        return tuple(
            sorted(
                opportunities,
                key=lambda o: o.confidence_score,
                reverse=True,
            )
        )

    # ------------------------------------------------------------------
    # Weak rankings
    # ------------------------------------------------------------------

    def _calculate_weak_rankings(
        self,
        analytics_result: SearchAnalyticsResult,
        competitor_rankings: tuple[CompetitorRanking, ...],
        target_domain: str,
    ) -> tuple[SearchOpportunity, ...]:
        """Calculate opportunities where target ranks but could be stronger.

        A weak ranking exists when:
        1. Target has observations for a keyword
        2. Target ranks but has a weaker position than competitors
        3. At least one competitor outranks the target
        """
        opportunities: list[SearchOpportunity] = []

        our_keyword_positions: dict[str, int | None] = {
            km.keyword: km.latest_position for km in analytics_result.keyword_metrics
        }

        competitors_by_keyword = self._group_by_keyword(competitor_rankings)

        for keyword, our_position in our_keyword_positions.items():
            if our_position is None or our_position > 50:
                continue

            competitors = competitors_by_keyword.get(keyword, [])

            relevant = [c for c in competitors if c.competitor_domain != target_domain]

            if not relevant:
                continue

            better = [c for c in relevant if c.position < our_position]

            if not better:
                continue

            worst_comp_pos = max(c.position for c in better)
            improvement_potential = our_position - worst_comp_pos

            km_index = next(
                i for i, km in enumerate(analytics_result.keyword_metrics) if km.keyword == keyword
            )
            confidence = min(
                analytics_result.keyword_metrics[km_index].observation_count / 10.0,
                1.0,
            )

            if improvement_potential >= 20:
                severity = "critical"
            elif improvement_potential >= 10:
                severity = "high"
            elif improvement_potential >= 5:
                severity = "medium"
            else:
                severity = "low"

            opportunities.append(
                SearchOpportunity(
                    keyword=keyword,
                    target_url="",
                    target_domain=target_domain,
                    competitor_domain=better[0].competitor_domain,
                    target_position=our_position,
                    competitor_position=None,
                    opportunity_type="weak_ranking",
                    severity=severity,
                    confidence_score=confidence,
                    estimated_improvement=(
                        f"Target ranks at position {our_position} for "
                        f"keyword '{keyword}', could improve by "
                        f"{improvement_potential} positions"
                    ),
                )
            )

        return tuple(
            sorted(
                opportunities,
                key=lambda o: o.confidence_score,
                reverse=True,
            )
        )

    # ------------------------------------------------------------------
    # Content gaps
    # ------------------------------------------------------------------

    def _calculate_content_gaps(
        self,
        analytics_result: SearchAnalyticsResult,
        competitor_rankings: tuple[CompetitorRanking, ...],
    ) -> tuple[ContentGapOpportunity, ...]:
        """Calculate content gaps through competitor analysis.

        A content gap exists when:
        1. Target has zero observations for a keyword (not ranking)
        2. Multiple competitors rank for that keyword
        3. Content opportunity exists for target site to create content
        """
        opportunities: list[ContentGapOpportunity] = []

        competitors_by_keyword = self._group_by_keyword(competitor_rankings)

        for keyword, competitors in competitors_by_keyword.items():
            # Skip if target already has observations for this keyword
            has_observations = any(
                km.keyword == keyword and km.observation_count > 0
                for km in analytics_result.keyword_metrics
            )
            if has_observations:
                continue

            distinct_domains = {c.competitor_domain for c in competitors}
            if len(distinct_domains) < 2:
                continue

            avg_position = sum(c.position for c in competitors) / len(competitors)

            sorted_competitors = sorted(competitors, key=lambda c: c.position)

            comp_domains = tuple(sorted({c.competitor_domain for c in competitors}))
            comp_urls = tuple(sorted({c.competitor_url for c in competitors}))
            comp_positions = tuple(c.position for c in sorted_competitors)

            confidence = min(len(distinct_domains) / 5.0, 1.0)

            content_description = None
            if avg_position <= 10:
                content_description = "High-volume commercial keyword"
            elif avg_position <= 20:
                content_description = "Mid-volume informational keyword"
            else:
                content_description = "Lower-volume niche keyword"

            primary_comp = sorted_competitors[0]

            opportunities.append(
                ContentGapOpportunity(
                    keyword=keyword,
                    target_domain="example.com",
                    competitor_domains=comp_domains,
                    competitor_urls=comp_urls,
                    competitor_positions=comp_positions,
                    average_competitor_position=avg_position,
                    primary_competitor=primary_comp.competitor_domain,
                    confidence_score=confidence,
                    content_description_hint=content_description,
                )
            )

        return tuple(
            sorted(
                opportunities,
                key=lambda o: o.average_competitor_position,
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _group_by_keyword(
        self, items: tuple[CompetitorRanking, ...]
    ) -> dict[str, list[CompetitorRanking]]:
        """Group items by keyword preserving input order within groups."""
        groups: dict[str, list[CompetitorRanking]] = {}
        for item in items:
            groups.setdefault(item.keyword, []).append(item)
        return groups


__all__ = [
    "ContentGapOpportunity",
    "SearchOpportunity",
    "SearchOpportunityResult",
    "SearchOpportunityService",
]
