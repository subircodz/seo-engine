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
    RankingObservation,
    SearchDataset,
)
from sie.domain.models.search_analytics import SearchAnalyticsResult
from sie.domain.models.search_serp import SERPFeatureType
from sie.domain.services.cannibalization import CannibalizationDetector
from sie.domain.services.ranking_volatility import RankingVolatilityService


@dataclass(frozen=True, slots=True)
class SearchOpportunity:
    """Actionable SEO opportunity derived from available evidence.

    Represents a specific keyword/URL combination with a ranking improvement potential,
    based on measurable data from competitor rankings or target ranking performance.
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
            raise ValueError(f"opportunity_type must be 'competitor_gap' or 'weak_ranking', got {self.opportunity_type}")

        if self.severity not in ("low", "medium", "high", "critical"):
            raise ValueError(f"severity must be one of 'low', 'medium', 'high', 'critical', got {self.severity}")

        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(f"confidence_score must be in [0.0, 1.0], got {self.confidence_score}")

        if self.opportunity_type == "competitor_gap" and self.target_position is None:
            raise ValueError("competitor_gap opportunity requires target_position to indicate target ranking status")

        if self.opportunity_type == "weak_ranking" and self.competitor_position is None:
            raise ValueError("weak_ranking opportunity requires competitor_position to indicate reference competitor position")

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

    Represents a keyword where competitors rank with content, but the target site
    is absent entirely, indicating a content opportunity.
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

        if len(self.competitor_domains) != len(self.competitor_urls) or len(self.competitor_urls) != len(self.competitor_positions):
            raise ValueError("competitor_domains, competitor_urls, and competitor_positions must have same length")

        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(f"confidence_score must be in [0.0, 1.0], got {self.confidence_score}")

    @property
    def competitor_count(self) -> int:
        return len(self.competitor_domains)

    @property
    def average_position_rank(self) -> str:
        avg = self.average_competitor_position
        if avg < 3:
            return "top_3"
        elif avg < 10:
            return "top_10"
        elif avg < 20:
            return "top_20"
        else:
            return "outside_top_20"

    def __lt__(self, other: ContentGapOpportunity) -> bool:
        return self.average_competitor_position < other.average_competitor_position


@dataclass(frozen=True, slots=True)
class SearchOpportunityResult:
    """Complete search opportunity analysis.

    Aggregates opportunities from multiple data sources into a single actionable result.
    """

    dataset_id: str
    competitor_gaps: tuple[SearchOpportunity, ...]
    weak_ranking_opportunities: tuple[SearchOpportunity, ...]
    content_gaps: tuple[ContentGapOpportunity, ...]
    total_opportunities: int

    @property
    def sorted_by_priority(self) -> SearchOpportunityResult:
        """Return result sorted by opportunity priority (severity + confidence)."""
        opps = list(self.competitor_gaps) + list(self.weak_ranking_opportunities)
        sorted_opps = tuple(sorted(opps, key=lambda o: (
            {"critical": 4, "high": 3, "medium": 2, "low": 1}[o.severity],
            o.confidence_score
        )))
        return SearchOpportunityResult(
            dataset_id=self.dataset_id,
            competitor_gaps=tuple(o for o in sorted_opps if o.is_competitor_gap),
            weak_ranking_opportunities=tuple(o for o in sorted_opps if o.is_weak_ranking),
            content_gaps=self.content_gaps,
            total_opportunities=self.total_opportunities,
        )


class SearchOpportunityService:
    """Domain service for calculating SEO search opportunities.

    This service implements Phase 6N-E opportunity analysis, providing actionable
    insights for SEO optimization based on measurable ranking and competitor data.

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

        Combines competitor gap analysis, weak ranking detection, and content gap
        identification into a single actionable result.
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
        content_gaps = self._calculate_content_gaps(
            analytics_result, competitor_rankings
        )

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
        # This would typically extract the target domain from dataset metadata
        # For now, we can derive it from observations' target_urls
        # This is a placeholder - actual implementation would depend on dataset structure
        return "example.com"

    def _calculate_competitor_gaps(
        self,
        analytics_result: SearchAnalyticsResult,
        competitor_rankings: tuple[CompetitorRanking, ...],
        target_domain: str,
    ) -> tuple[SearchOpportunity, ...]:
        """Calculate opportunities where competitors rank but target site does not.

        A competitor gap exists when:
        1. Target has at least one observation for a keyword
        2. Multiple competitors rank for that keyword
        3. Target is NOT ranking (no observation for that keyword)
        """
        opportunities = []

        # Get our keyword positions from keyword_metrics
        our_keyword_positions = {
            km.keyword: km.latest_position
            for km in analytics_result.keyword_metrics
        }

        # Group competitor rankings by keyword
        competitors_by_keyword = self._group_by_keyword(competitor_rankings)

        for keyword, competitors in competitors_by_keyword.items():
            # Skip if we don't have this keyword in our rankings
            if keyword not in our_keyword_positions:
                continue

            our_position = our_keyword_positions[keyword]

            # If target is already ranking, not a competitor gap
            if our_position is not None:
                continue

            # Get distinct competitor domains for this keyword
            distinct_competitor_domains = set(c.competitor_domain for c in competitors)

            # Skip if only one competitor (not a gap, just competition)
            if len(distinct_competitor_domains) < 2:
                continue

            # Get average competitor position
            avg_comp_pos = sum(c.position for c in competitors) / len(competitors)

            # Calculate confidence based on number of competitor observations
            confidence = min(len(competitors) / 10.0, 1.0)  # Scale up to 10 observations

            # Determine severity based on average position
            if avg_comp_pos <= 3:
                severity = "critical"
            elif avg_comp_pos <= 10:
                severity = "high"
            elif avg_comp_pos <= 20:
                severity = "medium"
            else:
                severity = "low"

            # Get URLs for reporting
            competitor_urls = tuple(sorted(set(c.competitor_url for c in competitors)))
            competitor_domains = tuple(sorted(set(c.competitor_domain for c in competitors)))

            # Get the primary (best ranking) competitor
            primary_comp = min(competitors, key=lambda c: c.position)

            opportunities.append(
                SearchOpportunity(
                    keyword=keyword,
                    target_url="",  # Would need to be derived from dataset
                    target_domain=target_domain,
                    competitor_domain=primary_comp.competitor_domain,
                    target_position=our_position,
                    competitor_position=primary_comp.position,
                    opportunity_type="competitor_gap",
                    severity=severity,
                    confidence_score=confidence,
                    estimated_improvement=f"Target site is not ranking for keyword '{keyword}'. Competitors average position: {avg_comp_pos:.1f}",
                )
            )

        return tuple(sorted(opportunities, key=lambda o: o.confidence_score, reverse=True))

    def _calculate_weak_rankings(
        self,
        analytics_result: SearchAnalyticsResult,
        competitor_rankings: tuple[CompetitorRanking, ...],
        target_domain: str,
    ) -> tuple[SearchOpportunity, ...]:
        """Calculate opportunities where target ranks but could be stronger.

        A weak ranking exists when:
        1. Target has observations for a keyword
        2. Target ranks but has weaker position than competitors
        3. At least one competitor outranks the target
        """
        opportunities = []

        # Get our keyword positions from keyword_metrics
        our_keyword_positions = {
            km.keyword: km.latest_position
            for km in analytics_result.keyword_metrics
        }

        # Group competitor rankings by keyword
        competitors_by_keyword = self._group_by_keyword(competitor_rankings)

        for keyword, our_position in our_keyword_positions.items():
            if our_position is None or our_position > 50:  # Not ranking well enough
                continue

            competitors = competitors_by_keyword.get(keyword, [])

            # Filter competitors to relevant domains only
            relevant_competitors = [c for c in competitors if c.competitor_domain != target_domain]

            if not relevant_competitors:
                continue

            # Find if any competitor outranks us
            better_competitors = [c for c in relevant_competitors if c.position < our_position]

            if not better_competitors:
                continue

            # Get worst competitor position
            worst_comp_pos = max(c.position for c in better_competitors)

            # Calculate improvement potential
            improvement_potential = our_position - worst_comp_pos

            # Calculate confidence based on observation count
            confidence = min(analytics_result.keyword_metrics[
                next(i for i, km in enumerate(analytics_result.keyword_metrics) if km.keyword == keyword)
            ].observation_count / 10.0, 1.0)

            # Determine severity based on improvement potential
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
                    target_url="",  # Would need to be derived from dataset
                    target_domain=target_domain,
                    competitor_domain=better_competitors[0].competitor_domain,
                    target_position=our_position,
                    competitor_position=better_competitors[0].position,
                    opportunity_type="weak_ranking",
                    severity=severity,
                    confidence_score=confidence,
                    estimated_improvement=f"Target ranks at position {our_position} for keyword '{keyword}', could improve by {improvement_potential} positions",
                )
            )

        return tuple(sorted(opportunities, key=lambda o: o.confidence_score, reverse=True))

    def _calculate_content_gaps(
        self,
        analytics_result: SearchAnalyticsResult,
        competitor_rankings: tuple[CompetitorRanking, ...],
    ) -> tuple[ContentGapOpportunity, ...]:
        """Calculate content gaps through competitor analysis.

        A content gap exists when:
        1. Target has no observations for a keyword (not ranking)
        2. Multiple competitors rank for that keyword
        3. Content opportunity exists for target site to create content
        """
        opportunities = []

        # Group competitor rankings by keyword
        competitors_by_keyword = self._group_by_keyword(competitor_rankings)

        for keyword, competitors in competitors_by_keyword.items():
            # Skip if target already has observations for this keyword
            has_observations = any(
                km.keyword == keyword for km in analytics_result.keyword_metrics
            )
            if has_observations:
                continue

            # Skip if fewer than 2 competitors
            distinct_competitor_domains = set(c.competitor_domain for c in competitors)
            if len(distinct_competitor_domains) < 2:
                continue

            # Calculate average competitor position
            avg_position = sum(c.position for c in competitors) / len(competitors)

            # Get sorted distinct competitors
            sorted_competitors = sorted(competitors, key=lambda c: c.position)

            # Build unique lists
            competitor_domains = tuple(sorted(set(c.competitor_domain for c in competitors)))
            competitor_urls = tuple(sorted(set(c.competitor_url for c in competitors)))
            competitor_positions = tuple(c.position for c in sorted_competitors)

            # Calculate confidence based on number of competing domains
            confidence = min(len(distinct_competitor_domains) / 5.0, 1.0)

            # Determine content description hint (simplified)
            content_description = None
            if avg_position <= 10:
                content_description = "High-volume commercial keyword"
            elif avg_position <= 20:
                content_description = "Mid-volume informational keyword"
            else:
                content_description = "Lower-volume niche keyword"

            # Determine primary competitor
            primary_comp = sorted_competitors[0]

            opportunities.append(
                ContentGapOpportunity(
                    keyword=keyword,
                    target_domain="example.com",  # Would need to be derived
                    competitor_domains=competitor_domains,
                    competitor_urls=competitor_urls,
                    competitor_positions=competitor_positions,
                    average_competitor_position=avg_position,
                    primary_competitor=primary_comp.competitor_domain,
                    confidence_score=confidence,
                    content_description_hint=content_description,
                )
            )

        return tuple(sorted(opportunities, key=lambda o: o.average_competitor_position))

    def _group_by_keyword(
        self, items: tuple[CompetitorRanking, ...]
    ) -> dict[str, list[CompetitorRanking]]:
        """Group items by keyword preserving input order within groups."""
        groups: dict[str, list[CompetitorRanking]] = {}
        for item in items:
            groups.setdefault(item.keyword, []).append(item)
        return groups


__all__ = [
    "SearchOpportunity",
    "ContentGapOpportunity",
    "SearchOpportunityResult",
    "SearchOpportunityService",
]