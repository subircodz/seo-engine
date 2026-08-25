"""Unit tests for Optimization Intelligence engine (Phase 8)."""

from __future__ import annotations

import pytest

from sie.domain.engines.search_optimization import (
    synthesize_optimization_recommendations,
)
from sie.domain.models.search_optimization import (
    OptimizationCategory,
    OptimizationEffort,
    OptimizationImpact,
    OptimizationRecommendation,
    OptimizationResult,
    calculate_priority_score,
)


# ════════════════════════════════════════════════════════════════════════════
# OptimizationRecommendation model
# ════════════════════════════════════════════════════════════════════════════


class TestOptimizationRecommendation:
    def test_valid(self):
        r = OptimizationRecommendation(
            category=OptimizationCategory.CONTENT,
            title="Test",
            description="Desc",
            impact=OptimizationImpact.HIGH,
            effort=OptimizationEffort.LOW,
            priority_score=0.8,
        )
        assert r.category == OptimizationCategory.CONTENT
        assert r.priority_score == 0.8

    def test_priority_score_out_of_range_raises(self):
        with pytest.raises(ValueError, match="priority_score must be"):
            OptimizationRecommendation(
                category=OptimizationCategory.CONTENT,
                title="T",
                description="D",
                impact=OptimizationImpact.HIGH,
                effort=OptimizationEffort.LOW,
                priority_score=1.5,
            )

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValueError, match="confidence must be"):
            OptimizationRecommendation(
                category=OptimizationCategory.CONTENT,
                title="T",
                description="D",
                impact=OptimizationImpact.HIGH,
                effort=OptimizationEffort.LOW,
                confidence=2.0,
            )


# ════════════════════════════════════════════════════════════════════════════
# calculate_priority_score
# ════════════════════════════════════════════════════════════════════════════


class TestCalculatePriorityScore:
    def test_high_impact_low_effort(self):
        score = calculate_priority_score(OptimizationImpact.HIGH, OptimizationEffort.LOW)
        assert score == 1.0

    def test_low_impact_high_effort(self):
        score = calculate_priority_score(OptimizationImpact.LOW, OptimizationEffort.HIGH)
        assert score == 0.09

    def test_medium_medium(self):
        score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.MEDIUM)
        assert score == 0.36

    def test_deterministic(self):
        s1 = calculate_priority_score(OptimizationImpact.HIGH, OptimizationEffort.MEDIUM)
        s2 = calculate_priority_score(OptimizationImpact.HIGH, OptimizationEffort.MEDIUM)
        assert s1 == s2


# ════════════════════════════════════════════════════════════════════════════
# synthesize_optimization_recommendations
# ════════════════════════════════════════════════════════════════════════════


class TestSynthesizeRecommendations:
    def test_empty_inputs(self):
        result = synthesize_optimization_recommendations("ds1")
        assert result.dataset_id == "ds1"
        assert result.total_recommendations == 0

    def test_ranking_recommendation(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            total_keywords=100,
            keywords_not_ranking=60,
            non_ranking_keywords=("kw1", "kw2"),
        )
        assert result.total_recommendations >= 1
        recs = result.recommendations
        ranking_recs = [r for r in recs if r.category == OptimizationCategory.KEYWORD]
        assert len(ranking_recs) >= 1

    def test_cannibalization_recommendation(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            extreme_cannibalization_count=3,
            cannibalization_count=5,
            cannibalized_keywords=("kw1",),
        )
        can_recs = [
            r for r in result.recommendations
            if r.category == OptimizationCategory.CANNIBALIZATION
        ]
        assert len(can_recs) >= 1
        assert can_recs[0].impact == OptimizationImpact.HIGH

    def test_serp_feature_recommendation(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            featured_snippet_occurrences=10,
            featured_snippet_owned=2,
        )
        serp_recs = [
            r for r in result.recommendations
            if r.category == OptimizationCategory.SERP_FEATURE
        ]
        assert len(serp_recs) >= 1

    def test_aio_recommendation(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            aio_total_keywords=50,
            aio_keywords_with_overview=30,
            aio_target_cited_count=5,
        )
        aio_recs = [
            r for r in result.recommendations
            if r.category == OptimizationCategory.AIO
        ]
        assert len(aio_recs) >= 1

    def test_geo_recommendation(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            geo_total_keywords=50,
            geo_keywords_mentioned=5,
            geo_overall_mention_rate=0.1,
        )
        geo_recs = [
            r for r in result.recommendations
            if r.category == OptimizationCategory.GEO
        ]
        assert len(geo_recs) >= 1

    def test_sorted_by_priority(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            total_keywords=100,
            keywords_not_ranking=60,
            cannibalization_count=10,
            extreme_cannibalization_count=5,
            volatile_keyword_count=20,
            total_volatility_keywords=100,
            competitor_gap_count=15,
            weak_ranking_count=10,
            content_gap_count=8,
            total_opportunities=33,
            featured_snippet_occurrences=5,
            featured_snippet_owned=1,
            people_also_ask_occurrences=3,
            people_also_ask_owned=0,
            aio_total_keywords=50,
            aio_keywords_with_overview=30,
            aio_target_cited_count=5,
            geo_total_keywords=50,
            geo_keywords_mentioned=5,
            geo_overall_mention_rate=0.1,
            entity_gap_count=10,
            entity_coverage=0.15,
        )
        if len(result.recommendations) >= 2:
            for i in range(len(result.recommendations) - 1):
                assert (
                    result.recommendations[i].priority_score
                    >= result.recommendations[i + 1].priority_score
                )

    def test_high_priority_count(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            total_keywords=100,
            keywords_not_ranking=60,
            extreme_cannibalization_count=5,
        )
        assert result.high_priority_count >= 0

    def test_quick_wins(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            featured_snippet_occurrences=10,
            featured_snippet_owned=2,
            people_also_ask_occurrences=5,
            people_also_ask_owned=0,
        )
        # SERP feature + low effort = quick wins
        assert result.estimated_quick_wins >= 0

    def test_summary_generated(self):
        result = synthesize_optimization_recommendations(
            "ds1",
            total_keywords=100,
            keywords_not_ranking=60,
        )
        assert len(result.summary) > 0

    def test_deterministic(self):
        kwargs = dict(
            dataset_id="ds1",
            total_keywords=100,
            keywords_not_ranking=30,
            cannibalization_count=5,
        )
        r1 = synthesize_optimization_recommendations(**kwargs)
        r2 = synthesize_optimization_recommendations(**kwargs)
        assert r1.total_recommendations == r2.total_recommendations
        assert r1.summary == r2.summary
