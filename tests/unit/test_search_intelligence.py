"""Unit tests for unified Search Intelligence Service (Phase 6N-H)."""

from datetime import UTC, datetime

import pytest

from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
)
from sie.domain.services.search_intelligence import (
    RecommendationCategory,
    RecommendationPriority,
    SearchIntelligenceResult,
    SearchIntelligenceService,
    SearchRecommendation,
)

_T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def _obs(keyword="kw", url="https://oursite.io/", position=5, observed_at=_T0):
    return RankingObservation(
        keyword=keyword,
        target_url=url,
        position=position,
        source="gsc",
        device=SearchDevice.DESKTOP,
        search_engine="google",
        country="us",
        language="en",
        observed_at=observed_at,
    )


def _comp(keyword="kw", domain="comp1.com", url="https://comp1.com/", position=3, observed_at=_T0):
    return CompetitorRanking(
        keyword=keyword,
        competitor_domain=domain,
        competitor_url=url,
        position=position,
        observed_at=observed_at,
    )


def _dataset(dataset_id="ds-1", total_keywords=5, total_observations=10):
    return SearchDataset(
        dataset_id=dataset_id,
        name="test",
        source="test",
        total_keywords=total_keywords,
        total_observations=total_observations,
    )


# ── Recommendation model tests ──────────────────────────────────────────


class TestSearchRecommendation:
    def test_valid_recommendation(self):
        rec = SearchRecommendation(
            category=RecommendationCategory.RANKING,
            priority=RecommendationPriority.HIGH,
            title="Test",
            description="Test description",
        )
        assert rec.category == RecommendationCategory.RANKING
        assert rec.priority == RecommendationPriority.HIGH
        assert rec.confidence == 0.5

    def test_confidence_bounds(self):
        with pytest.raises(ValueError, match="confidence"):
            SearchRecommendation(
                category=RecommendationCategory.RANKING,
                priority=RecommendationPriority.HIGH,
                title="Test",
                description="Test",
                confidence=1.5,
            )

    def test_negative_confidence_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            SearchRecommendation(
                category=RecommendationCategory.RANKING,
                priority=RecommendationPriority.HIGH,
                title="Test",
                description="Test",
                confidence=-0.1,
            )


# ── Service tests ───────────────────────────────────────────────────────


class TestSearchIntelligenceService:
    def test_analyze_empty_dataset(self):
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=0, total_observations=0)
        result = service.analyze(dataset, (), ())

        assert isinstance(result, SearchIntelligenceResult)
        assert result.dataset_id == "ds-1"
        assert result.summary.total_keywords == 0
        assert result.summary.keywords_ranking == 0

    def test_analyze_with_observations(self):
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=2, total_observations=4)
        observations = (
            _obs(keyword="kw1", position=3),
            _obs(keyword="kw1", position=5, observed_at=_T1),
            _obs(keyword="kw2", position=15),
            _obs(keyword="kw2", position=20, observed_at=_T1),
        )
        competitors = (
            _comp(keyword="kw1", domain="comp1.com", position=2),
            _comp(keyword="kw1", domain="comp2.com", position=7),
        )

        result = service.analyze(dataset, observations, competitors)

        assert result.summary.total_keywords == 2
        assert result.summary.keywords_ranking == 2
        assert result.summary.visibility_score > 0
        assert result.analytics is not None

    def test_cannibalization_detection(self):
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=1, total_observations=3)
        observations = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=5),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=8),
            _obs(keyword="kw1", url="https://oursite.io/page3", position=12),
        )

        result = service.analyze(dataset, observations, ())

        assert result.summary.cannibalization_count > 0
        assert len(result.cannibalization_findings) > 0

    def test_volatility_detection(self):
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=1, total_observations=4)
        observations = (
            _obs(keyword="kw1", position=2),
            _obs(keyword="kw1", position=20, observed_at=_T1),
        )

        result = service.analyze(dataset, observations, ())

        assert result.volatility_metrics is not None

    def test_competitor_gap_opportunity(self):
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=1, total_observations=1)
        observations = (_obs(keyword="kw1", position=5),)
        competitors = (
            _comp(keyword="kw1", domain="comp1.com", position=3),
            _comp(keyword="kw1", domain="comp2.com", position=7),
        )

        result = service.analyze(dataset, observations, competitors)

        # The service should produce recommendations
        assert len(result.recommendations) > 0

    def test_recommendations_sorted_by_priority(self):
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=0, total_observations=0)
        result = service.analyze(dataset, (), ())

        # All recommendations should be sorted by priority
        priorities = [r.priority for r in result.recommendations]
        priority_values = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        for i in range(len(priorities) - 1):
            assert priority_values[priorities[i]] <= priority_values[priorities[i + 1]]

    def test_recommendations_have_required_fields(self):
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=2, total_observations=4)
        observations = (
            _obs(keyword="kw1", position=3),
            _obs(keyword="kw2", position=15),
        )

        result = service.analyze(dataset, observations, ())

        for rec in result.recommendations:
            assert rec.category is not None
            assert rec.priority is not None
            assert rec.title
            assert rec.description
            assert 0.0 <= rec.confidence <= 1.0
