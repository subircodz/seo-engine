"""Industry Intelligence Service (Phase 11 - Integration Layer).

Orchestrates industry-specific intelligence synthesis by connecting:
- Existing search datasets
- Existing SEO intelligence
- Casino, Crypto, Crypto-Casino engines (Phase 9)
- Industry synthesis engine (Phase 10)

Produces deterministic, actionable industry intelligence results.
"""

from __future__ import annotations

from dataclasses import dataclass

from sie.domain.engines.industry_synthesis import (
    generate_industry_intelligence,
)
from sie.domain.models.industry import (
    IndustryIntelligenceResult,
    IndustryProfile,
    IndustryType,
)
from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
)


@dataclass(frozen=True, slots=True)
class IndustryAnalysisConfig:
    """Configuration for industry intelligence analysis."""

    industry_type: IndustryType = IndustryType.GENERAL
    target_domain: str = ""
    include_entity_analysis: bool = True
    include_opportunity_scoring: bool = True
    min_entity_confidence: float = 0.5
    min_opportunity_priority: float = 0.5


class IndustryIntelligenceService:
    """Orchestrates industry intelligence synthesis from existing data.

    This service connects the existing search intelligence capabilities
    with industry-specific analysis engines to produce actionable
    industry intelligence results.
    """

    def analyze_from_dataset(
        self,
        dataset: SearchDataset,
        observations: tuple[RankingObservation, ...] = (),
        competitor_rankings: tuple[CompetitorRanking, ...] = (),
        config: IndustryAnalysisConfig | None = None,
    ) -> IndustryIntelligenceResult:
        """Generate industry intelligence from a search dataset.

        This method takes an existing search dataset and produces
        industry-specific intelligence analysis using the Phase 9
        and Phase 10 engines.

        Args:
            dataset: The search dataset to analyze
            observations: Ranking observations for the dataset
            competitor_rankings: Competitor rankings for the domain
            config: Industry analysis configuration

        Returns:
            IndustryIntelligenceResult with findings and opportunities
        """
        profile = self._build_profile(config or IndustryAnalysisConfig())
        return generate_industry_intelligence(
            profile=profile,
            total_keywords=dataset.total_keywords,
            keywords_not_ranking=self._count_keywords_not_ranking(observations),
            visibility_score=self._calculate_visibility_score(observations, dataset.total_keywords),
            entity_coverage=self._estimate_entity_coverage(observations),
            content=self._extract_content_signals(observations),
            competitor_domains=tuple(cr.competitor_domain for cr in competitor_rankings),
            keywords=tuple(obs.keyword for obs in observations if hasattr(obs, "keyword")),
        )

    def analyze_with_content(
        self,
        dataset: SearchDataset,
        content: str,
        observations: tuple[RankingObservation, ...] = (),
        competitor_rankings: tuple[CompetitorRanking, ...] = (),
        config: IndustryAnalysisConfig | None = None,
    ) -> IndustryIntelligenceResult:
        """Generate industry intelligence with explicit content input.

        This method allows passing industry-relevant content directly,
        which is useful when you have crawled content that should be
        analyzed for industry-specific insights.

        Args:
            dataset: The search dataset
            content: Industry-relevant content to analyze
            observations: Ranking observations
            competitor_rankings: Competitor data
            config: Analysis configuration

        Returns:
            IndustryIntelligenceResult
        """
        profile = self._build_profile(config or IndustryAnalysisConfig())
        return generate_industry_intelligence(
            profile=profile,
            total_keywords=dataset.total_keywords,
            keywords_not_ranking=self._count_keywords_not_ranking(observations),
            visibility_score=self._calculate_visibility_score(observations, dataset.total_keywords),
            entity_coverage=self._estimate_entity_coverage(observations),
            content=content,
            competitor_domains=tuple(cr.competitor_domain for cr in competitor_rankings),
            keywords=tuple(o.keyword for o in observations if hasattr(o, "keyword")),
        )

    def _build_profile(self, config: IndustryAnalysisConfig) -> IndustryProfile:
        """Build an IndustryProfile from configuration."""
        return IndustryProfile(
            industry_type=config.industry_type,
            target_domain=config.target_domain,
            include_entity_analysis=config.include_entity_analysis,
            include_opportunity_scoring=config.include_opportunity_scoring,
            min_entity_confidence=config.min_entity_confidence,
            min_opportunity_priority=config.min_opportunity_priority,
        )

    def _count_keywords_not_ranking(self, observations: tuple[RankingObservation, ...]) -> int:
        """Count keywords that have no ranking observation."""
        ranking_keywords = {obs.keyword for obs in observations if hasattr(obs, "keyword")}
        return len(ranking_keywords)

    def _calculate_visibility_score(
        self, observations: tuple[RankingObservation, ...], total_keywords: int
    ) -> float:
        """Estimate visibility score from observations."""
        if total_keywords == 0 or not observations:
            return 0.0

        ranking_obs = [o for o in observations if hasattr(o, "position") and o.position <= 10]
        ranking_count = len(ranking_obs)
        return round(ranking_count / total_keywords, 3) if total_keywords > 0 else 0.0

    def _estimate_entity_coverage(self, observations: tuple[RankingObservation, ...]) -> float:
        """Estimate entity coverage from observations."""
        if not observations:
            return 0.0
        kw = set(o.keyword for o in observations if hasattr(o, "keyword"))
        return round(min(len(kw) / max(len(observations), 1), 1.0), 3)

    def _extract_content_signals(self, observations: tuple[RankingObservation, ...]) -> str:
        """Extract content signals from observations for entity analysis."""
        content_parts = []
        for obs in observations:
            if hasattr(obs, "keyword"):
                content_parts.append(obs.keyword)
        return " ".join(content_parts) if content_parts else ""
