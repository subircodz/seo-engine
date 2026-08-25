"""Unit tests for Search Opportunity Intelligence (Phase 6N-E)."""

import dataclasses
from datetime import UTC, datetime

import pytest

from sie.domain.engines.search_analytics import SearchAnalyticsResult
from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
)
from sie.domain.models.search_analytics import DatasetSearchMetrics, KeywordRankingMetrics
from sie.domain.services.search_opportunity import (
    ContentGapOpportunity,
    SearchOpportunity,
    SearchOpportunityResult,
    SearchOpportunityService,
)

_T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def _obs(keyword="kw", url="https://oursite.io/", position=5, observed_at=_T0, keyword_norm=None):
    return RankingObservation(
        keyword=keyword,
        keyword_norm=keyword_norm or keyword,
        target_url=url,
        position=position,
        source="gsc",
        device=SearchDevice.DESKTOP,
        search_engine="google",
        country="us",
        language="en",
        observed_at=observed_at,
    )


def _comp(keywords, domains, urls, positions, observed_at=_T0):
    return tuple(
        CompetitorRanking(
            keyword=kw,
            competitor_domain=dom,
            competitor_url=url,
            position=pos,
            observed_at=observed_at,
        )
        for kw, dom, url, pos in zip(keywords, domains, urls, positions, strict=False)
    )


def _dataset(dataset_id="ds-1", total_keywords=0, total_observations=0):
    return SearchDataset(
        dataset_id=dataset_id,
        name="fixture",
        source="test",
        total_keywords=total_keywords,
        total_observations=total_observations,
    )


def _analytics_result(keyword_metrics):
    return SearchAnalyticsResult(
        dataset_id="ds-1",
        keyword_metrics=tuple(keyword_metrics),
        dataset_metrics=DatasetSearchMetrics(
            dataset_id="ds-1",
            total_keywords=10,
            total_observations=5,
            keywords_with_rankings=5,
            keywords_not_ranking=5,
            average_position=5.0,
            median_position=5.0,
            top_3_count=1,
            top_10_count=3,
            top_20_count=5,
            top_50_count=5,
            visibility_score=0.7,
            total_serp_feature_occurrences=0,
            serp_features_by_type={},
            observations_with_serp_features=0,
            featured_snippet_occurrences=0,
            people_also_ask_occurrences=0,
            featured_snippet_owned_by_target=0,
            people_also_ask_owned_by_target=0,
            keywords_with_featured_snippet=0,
            keywords_with_people_also_ask=0,
        ),
        competitor_metrics=(),
    )


class TestSearchOpportunityModels:
    def test_search_opportunity_valid(self):
        opp = SearchOpportunity(
            keyword="test keyword",
            target_url="https://oursite.io/page",
            target_domain="oursite.io",
            competitor_domain="competitor.com",
            target_position=5,
            competitor_position=2,
            opportunity_type="competitor_gap",
            severity="high",
            confidence_score=0.8,
            estimated_improvement="Test improvement",
        )
        assert opp.keyword == "test keyword"
        assert opp.target_domain == "oursite.io"
        assert opp.competitor_domain == "competitor.com"
        assert opp.target_position == 5
        assert opp.competitor_position == 2
        assert opp.is_competitor_gap
        assert not opp.is_weak_ranking
        assert opp.severity == "high"
        assert opp.confidence_score == 0.8

    def test_search_opportunity_weak_ranking(self):
        opp = SearchOpportunity(
            keyword="test keyword",
            target_url="https://oursite.io/page",
            target_domain="oursite.io",
            competitor_domain="competitor.com",
            target_position=10,
            competitor_position=None,
            opportunity_type="weak_ranking",
            severity="medium",
            confidence_score=0.5,
            estimated_improvement="Test weak ranking improvement",
        )
        assert opp.is_weak_ranking
        assert not opp.is_competitor_gap
        assert opp.target_position == 10
        assert opp.competitor_position is None

    def test_search_opportunity_validation(self):
        with pytest.raises(ValueError, match="opportunity_type"):
            SearchOpportunity(
                keyword="test",
                target_url="https://oursite.io/page",
                target_domain="oursite.io",
                competitor_domain="competitor.com",
                target_position=None,
                competitor_position=None,
                opportunity_type="invalid",
                severity="high",
                confidence_score=0.5,
                estimated_improvement="test",
            )

        with pytest.raises(ValueError, match="severity"):
            SearchOpportunity(
                keyword="test",
                target_url="https://oursite.io/page",
                target_domain="oursite.io",
                competitor_domain="competitor.com",
                target_position=None,
                competitor_position=None,
                opportunity_type="competitor_gap",
                severity="invalid",
                confidence_score=0.5,
                estimated_improvement="test",
            )

        with pytest.raises(ValueError, match="confidence_score"):
            SearchOpportunity(
                keyword="test",
                target_url="https://oursite.io/page",
                target_domain="oursite.io",
                competitor_domain="competitor.com",
                target_position=None,
                competitor_position=None,
                opportunity_type="competitor_gap",
                severity="high",
                confidence_score=1.5,
                estimated_improvement="test",
            )

    def test_search_opportunity_competitor_gap_validation(self):
        with pytest.raises(ValueError, match="target_position"):
            SearchOpportunity(
                keyword="test",
                target_url="https://oursite.io/page",
                target_domain="oursite.io",
                competitor_domain="competitor.com",
                target_position=3,
                competitor_position=None,
                opportunity_type="competitor_gap",
                severity="high",
                confidence_score=0.5,
                estimated_improvement="test",
            )

    def test_search_opportunity_weak_ranking_validation(self):
        with pytest.raises(ValueError, match="competitor_position"):
            SearchOpportunity(
                keyword="test",
                target_url="https://oursite.io/page",
                target_domain="oursite.io",
                competitor_domain="competitor.com",
                target_position=3,
                competitor_position=2,
                opportunity_type="weak_ranking",
                severity="high",
                confidence_score=0.5,
                estimated_improvement="test",
            )

    def test_search_opportunity_frozen(self):
        opp = SearchOpportunity(
            keyword="test keyword",
            target_url="https://oursite.io/page",
            target_domain="oursite.io",
            competitor_domain="competitor.com",
            target_position=5,
            competitor_position=2,
            opportunity_type="competitor_gap",
            severity="high",
            confidence_score=0.8,
            estimated_improvement="Test improvement",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            opp.keyword = "other"  # type: ignore

    def test_content_gap_valid(self):
        gap = ContentGapOpportunity(
            keyword="missing content",
            target_domain="oursite.io",
            competitor_domains=("competitor1.com", "competitor2.com"),
            competitor_urls=("https://comp1.com/page", "https://comp2.com/page"),
            competitor_positions=(3, 7),
            average_competitor_position=5.0,
            primary_competitor="competitor1.com",
            confidence_score=0.8,
            content_description_hint="High potential opportunity",
        )
        assert gap.keyword == "missing content"
        assert gap.target_domain == "oursite.io"
        assert gap.competitor_count == 2
        assert gap.average_position_rank == "top_10"
        assert gap.content_description_hint == "High potential opportunity"

    def test_content_gap_validation(self):
        with pytest.raises(ValueError, match="competitor_domains"):
            ContentGapOpportunity(
                keyword="test",
                target_domain="oursite.io",
                competitor_domains=(),
                competitor_urls=(),
                competitor_positions=(),
                average_competitor_position=5.0,
                primary_competitor="comp.com",
                confidence_score=0.5,
            )

        with pytest.raises(ValueError, match="competitor_domains"):
            ContentGapOpportunity(
                keyword="test",
                target_domain="oursite.io",
                competitor_domains=("comp1.com", "comp2.com"),
                competitor_urls=("https://comp1.com"),
                competitor_positions=(3,),
                average_competitor_position=5.0,
                primary_competitor="comp1.com",
                confidence_score=0.5,
            )

    def test_content_gap_ordering(self):
        gap1 = ContentGapOpportunity(
            keyword="kw1",
            target_domain="oursite.io",
            competitor_domains=("comp1.com",),
            competitor_urls=("https://comp1.com/page",),
            competitor_positions=(3,),
            average_competitor_position=3.0,
            primary_competitor="comp1.com",
            confidence_score=0.8,
        )
        gap2 = ContentGapOpportunity(
            keyword="kw2",
            target_domain="oursite.io",
            competitor_domains=("comp1.com",),
            competitor_urls=("https://comp1.com/page",),
            competitor_positions=(10,),
            average_competitor_position=10.0,
            primary_competitor="comp1.com",
            confidence_score=0.8,
        )
        assert gap1 < gap2
        assert gap1.average_position_rank == "top_3"
        assert gap2.average_position_rank == "outside_top_20"


class TestSearchOpportunityResult:
    def test_sorted_by_priority(self):
        opp1 = SearchOpportunity(
            keyword="low priority",
            target_url="https://oursite.io/page1",
            target_domain="oursite.io",
            competitor_domain="comp.com",
            target_position=None,
            competitor_position=2,
            opportunity_type="competitor_gap",
            severity="low",
            confidence_score=0.3,
            estimated_improvement="Low priority",
        )
        opp2 = SearchOpportunity(
            keyword="high priority",
            target_url="https://oursite.io/page2",
            target_domain="oursite.io",
            competitor_domain="comp.com",
            target_position=None,
            competitor_position=5,
            opportunity_type="competitor_gap",
            severity="critical",
            confidence_score=0.9,
            estimated_improvement="High priority",
        )
        opp3 = SearchOpportunity(
            keyword="medium priority",
            target_url="https://oursite.io/page3",
            target_domain="oursite.io",
            competitor_domain="comp.com",
            target_position=10,
            competitor_position=None,
            opportunity_type="weak_ranking",
            severity="medium",
            confidence_score=0.7,
            estimated_improvement="Medium priority",
        )

        result = SearchOpportunityResult(
            dataset_id="ds-1",
            competitor_gaps=(opp1, opp2),
            weak_ranking_opportunities=(opp3,),
            content_gaps=(),
            total_opportunities=3,
        )

        sorted_result = result.sorted_by_priority
        # opp2 should come first (critical + high confidence)
        # then opp3 (medium)
        # then opp1 (low)
        assert sorted_result.competitor_gaps[0] == opp2
        assert sorted_result.competitor_gaps[1] == opp1
        assert sorted_result.weak_ranking_opportunities[0] == opp3


class TestSearchOpportunityService:
    def test_calculate_competitor_gaps(self):
        service = SearchOpportunityService()

        analytics_result = _analytics_result(
            [
                KeywordRankingMetrics(
                    keyword="kw1",
                    observation_count=2,
                    best_position=3,
                    worst_position=3,
                    average_position=3.0,
                    latest_position=None,
                    first_position=3,
                    position_change=None,
                    improved=False,
                    declined=False,
                ),
                KeywordRankingMetrics(
                    keyword="kw2",
                    observation_count=1,
                    best_position=10,
                    worst_position=10,
                    average_position=10.0,
                    latest_position=None,
                    first_position=10,
                    position_change=None,
                    improved=False,
                    declined=False,
                ),
            ]
        )

        competitor_rankings = _comp(
            keywords=["kw1", "kw1", "kw2", "kw2"],
            domains=["comp1.com", "comp2.com", "comp1.com", "comp2.com"],
            urls=[
                "https://comp1.com/page1",
                "https://comp2.com/page2",
                "https://comp1.com/page3",
                "https://comp2.com/page4",
            ],
            positions=[2, 7, 3, 8],
        )

        result = service._calculate_competitor_gaps(
            analytics_result, competitor_rankings, "oursite.io"
        )

        # Should only return kw2 (target has no observation, multiple competitors)
        assert len(result) == 1
        assert result[0].keyword == "kw2"
        assert result[0].is_competitor_gap
        assert result[0].target_position is None
        assert result[0].severity in ("low", "medium", "high", "critical")
        assert 0.0 <= result[0].confidence_score <= 1.0

    def test_calculate_weak_rankings(self):
        service = SearchOpportunityService()

        analytics_result = _analytics_result(
            [
                KeywordRankingMetrics(
                    keyword="kw1",
                    observation_count=2,
                    best_position=3,
                    worst_position=10,
                    average_position=6.5,
                    latest_position=10,
                    first_position=3,
                    position_change=-7,
                    improved=False,
                    declined=True,
                ),
                KeywordRankingMetrics(
                    keyword="kw2",
                    observation_count=1,
                    best_position=15,
                    worst_position=15,
                    average_position=15.0,
                    latest_position=15,
                    first_position=15,
                    position_change=None,
                    improved=False,
                    declined=False,
                ),
            ]
        )

        competitor_rankings = _comp(
            keywords=["kw1", "kw1"],
            domains=["comp1.com", "oursite.io"],
            urls=["https://comp1.com/page1", "https://oursite.io/page2"],
            positions=[3, 7],
        )

        result = service._calculate_weak_rankings(
            analytics_result, competitor_rankings, "oursite.io"
        )

        # Should only return kw1 (target ranks but competitor outranks)
        assert len(result) == 1
        assert result[0].keyword == "kw1"
        assert result[0].is_weak_ranking
        assert result[0].target_position == 10
        assert result[0].competitor_position is None

    def test_calculate_content_gaps(self):
        service = SearchOpportunityService()

        analytics_result = _analytics_result(
            [
                KeywordRankingMetrics(
                    keyword="kw1",
                    observation_count=1,
                    best_position=5,
                    worst_position=5,
                    average_position=5.0,
                    latest_position=5,
                    first_position=5,
                    position_change=None,
                    improved=False,
                    declined=False,
                ),
                KeywordRankingMetrics(
                    keyword="kw2",
                    observation_count=0,
                    best_position=0,
                    worst_position=0,
                    average_position=0.0,
                    latest_position=0,
                    first_position=0,
                    position_change=None,
                    improved=False,
                    declined=False,
                ),
            ]
        )

        competitor_rankings = _comp(
            keywords=["kw2", "kw2"],
            domains=["comp1.com", "comp2.com"],
            urls=["https://comp1.com/page1", "https://comp2.com/page2"],
            positions=[3, 7],
        )

        result = service._calculate_content_gaps(analytics_result, competitor_rankings)

        # Should only return kw2 (no target observations, multiple competitors)
        assert len(result) == 1
        assert result[0].keyword == "kw2"
        assert result[0].competitor_count == 2
        assert result[0].average_competitor_position == 5.0
        assert result[0].average_position_rank == "top_10"
        assert 0.0 <= result[0].confidence_score <= 1.0

    def test_group_by_keyword(self):
        service = SearchOpportunityService()

        items = _comp(
            keywords=["kw1", "kw2", "kw1", "kw2"],
            domains=["comp1.com", "comp2.com", "comp3.com", "comp4.com"],
            urls=[
                "https://comp1.com",
                "https://comp2.com",
                "https://comp3.com",
                "https://comp4.com",
            ],
            positions=[3, 5, 7, 9],
        )

        groups = service._group_by_keyword(items)

        assert "kw1" in groups
        assert "kw2" in groups
        assert len(groups["kw1"]) == 2
        assert len(groups["kw2"]) == 2
        assert groups["kw1"][0].competitor_domain == "comp1.com"
        assert groups["kw1"][1].competitor_domain == "comp3.com"
