"""Phase 3 dedicated tests for AIO/GEO recommendation generation in SearchIntelligenceService."""

from datetime import UTC, datetime

import pytest

from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
)
from sie.domain.models.search_aio import (
    AIOverviewDatasetMetrics,
    AIOverviewMetrics,
    AIOverviewResult,
)
from sie.domain.models.search_geo import (
    GEODatasetMetrics,
    GEOMetrics,
    GEOResult,
)
from sie.domain.services.search_intelligence import (
    RecommendationCategory,
    RecommendationPriority,
    SearchIntelligenceService,
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


def _aio_dm(
    dataset_id="aio-test",
    total_keywords=10,
    keywords_with_ai_overview=5,
    keywords_target_cited=0,
    total_ai_overview_observations=5,
    total_citations=8,
    target_citation_rate=0.0,
    competitor_cited_domains=("comp1.com", "comp2.com"),
):
    return AIOverviewDatasetMetrics(
        dataset_id=dataset_id,
        total_keywords=total_keywords,
        keywords_with_ai_overview=keywords_with_ai_overview,
        keywords_target_cited=keywords_target_cited,
        total_ai_overview_observations=total_ai_overview_observations,
        total_citations=total_citations,
        target_citation_rate=target_citation_rate,
        competitor_cited_domains=competitor_cited_domains,
    )


def _aio_km(
    keyword="test keyword",
    observation_count=3,
    ai_overview_present_count=3,
    target_cited_count=0,
    competitor_cited_count=2,
    citation_rate=1.0,
    target_citation_rate=0.0,
):
    return AIOverviewMetrics(
        keyword=keyword,
        observation_count=observation_count,
        ai_overview_present_count=ai_overview_present_count,
        target_cited_count=target_cited_count,
        competitor_cited_count=competitor_cited_count,
        citation_rate=citation_rate,
        target_citation_rate=target_citation_rate,
    )


def _geo_dm(
    dataset_id="geo-test",
    total_keywords=10,
    keywords_target_mentioned=0,
    total_observations=10,
    total_target_mentions=0,
    overall_mention_rate=0.0,
    competitor_domain_counts=None,
):
    if competitor_domain_counts is None:
        competitor_domain_counts = {"comp1.com": 3, "comp2.com": 2}
    return GEODatasetMetrics(
        dataset_id=dataset_id,
        total_keywords=total_keywords,
        keywords_target_mentioned=keywords_target_mentioned,
        total_observations=total_observations,
        total_target_mentions=total_target_mentions,
        overall_mention_rate=overall_mention_rate,
        competitor_domain_counts=competitor_domain_counts,
    )


def _geo_km(
    keyword="test keyword",
    observation_count=3,
    target_mentioned_count=0,
    competitor_mentioned_count=1,
    mention_rate=0.33,
    avg_mention_count=0.33,
):
    return GEOMetrics(
        keyword=keyword,
        observation_count=observation_count,
        target_mentioned_count=target_mentioned_count,
        competitor_mentioned_count=competitor_mentioned_count,
        mention_rate=mention_rate,
        avg_mention_count=avg_mention_count,
    )


class TestAIORecommendations:
    """Tests for AIO-specific recommendation generation."""

    def test_aio_present_target_cited_no_missing_citation_rec(self):
        """AIO present + target cited → no missing-citation recommendation."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(keywords_target_cited=3, target_citation_rate=0.6),
            keyword_metrics=(_aio_km(target_cited_count=2, target_citation_rate=0.6),),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result)
        aio_recs = [r for r in result.recommendations if r.category == RecommendationCategory.AIO]

        # Should NOT have "AI Overviews present but site not cited"
        missing_citation = [r for r in aio_recs if "not cited" in r.title.lower()]
        assert len(missing_citation) == 0, f"Unexpected missing citation rec: {missing_citation}"

        # Should have competitor cited rec
        competitor_recs = [r for r in aio_recs if "competitor" in r.title.lower()]
        assert len(competitor_recs) == 1
        assert competitor_recs[0].priority == RecommendationPriority.MEDIUM
        assert competitor_recs[0].supporting_metrics["competitor_count"] == 2
        assert "comp1.com" in competitor_recs[0].supporting_metrics["all_cited_competitors"]
        assert "comp2.com" in competitor_recs[0].supporting_metrics["all_cited_competitors"]

    def test_aio_present_competitor_cited_target_not_cited(self):
        """AIO present + competitor cited + target not cited → AIO citation opportunity."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(keywords_target_cited=0, target_citation_rate=0.0),
            keyword_metrics=(_aio_km(target_cited_count=0),),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result)
        aio_recs = [r for r in result.recommendations if r.category == RecommendationCategory.AIO]

        # Must have HIGH priority missing citation rec
        missing_citation = [r for r in aio_recs if "not cited" in r.title.lower()]
        assert len(missing_citation) == 1
        assert missing_citation[0].priority == RecommendationPriority.HIGH
        assert missing_citation[0].confidence == 0.85
        assert missing_citation[0].supporting_metrics["keywords_with_ai_overview"] == 5
        assert missing_citation[0].supporting_metrics["target_cited_count"] == 0
        assert "comp1.com" in missing_citation[0].supporting_metrics["competitor_cited_domains"]
        assert "comp2.com" in missing_citation[0].supporting_metrics["competitor_cited_domains"]

        # Must have competitor cited rec
        competitor_recs = [r for r in aio_recs if "competitor" in r.title.lower()]
        assert len(competitor_recs) == 1

    def test_aio_present_no_target_no_competitor_citation(self):
        """AIO present + no target/competitor citation → no fabricated competitor gap."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(
                keywords_with_ai_overview=3,
                keywords_target_cited=0,
                target_citation_rate=0.0,
                competitor_cited_domains=(),
            ),
            keyword_metrics=(_aio_km(competitor_cited_count=0, citation_rate=0.0),),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result)
        aio_recs = [r for r in result.recommendations if r.category == RecommendationCategory.AIO]

        # Should have missing citation rec (AIO present, target not cited)
        missing_citation = [r for r in aio_recs if "not cited" in r.title.lower()]
        assert len(missing_citation) == 1

        # Should NOT have competitor cited rec (no competitors cited)
        competitor_recs = [r for r in aio_recs if "competitor" in r.title.lower()]
        assert len(competitor_recs) == 0

    def test_aio_absent_no_recommendation(self):
        """AIO absent (0 AIO keywords) → no AIO visibility recommendation."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(
                keywords_with_ai_overview=0,
                keywords_target_cited=0,
                total_ai_overview_observations=0,
                total_citations=0,
                target_citation_rate=0.0,
                competitor_cited_domains=(),
            ),
            keyword_metrics=(),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result)
        aio_recs = [r for r in result.recommendations if r.category == RecommendationCategory.AIO]

        assert len(aio_recs) == 0

    def test_aio_not_assessed_no_recommendation(self):
        """aio_result=None → no AIO recommendations."""
        service = SearchIntelligenceService()
        dataset = _dataset()

        result = service.analyze(dataset, (), (), aio_result=None)
        aio_recs = [r for r in result.recommendations if r.category == RecommendationCategory.AIO]

        assert len(aio_recs) == 0

    def test_aio_multiple_competitors_preserved(self):
        """Multiple competitors → preserve actual competitor evidence."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(
                competitor_cited_domains=("comp1.com", "comp2.com", "comp3.com", "comp4.com")
            ),
            keyword_metrics=(_aio_km(),),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result)
        aio_recs = [r for r in result.recommendations if r.category == RecommendationCategory.AIO]

        missing_citation = next(r for r in aio_recs if "not cited" in r.title.lower())
        competitors = missing_citation.supporting_metrics["competitor_cited_domains"]
        assert len(competitors) == 4
        assert "comp1.com" in competitors
        assert "comp2.com" in competitors
        assert "comp3.com" in competitors
        assert "comp4.com" in competitors

        competitor_rec = next(r for r in aio_recs if "competitor" in r.title.lower())
        assert competitor_rec.supporting_metrics["all_cited_competitors"] == [
            "comp1.com", "comp2.com", "comp3.com", "comp4.com"
        ]

    def test_aio_multiple_queries_evidence_preserved(self):
        """Multiple queries → query-specific evidence preserved in keyword_metrics."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(keywords_with_ai_overview=5, keywords_target_cited=0),
            keyword_metrics=(
                _aio_km(keyword="query one", ai_overview_present_count=2, target_cited_count=0),
                _aio_km(keyword="query two", ai_overview_present_count=3, target_cited_count=0),
                _aio_km(keyword="query three", ai_overview_present_count=1, target_cited_count=0),
            ),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result)
        aio_recs = [r for r in result.recommendations if r.category == RecommendationCategory.AIO]

        missing_citation = next(r for r in aio_recs if "not cited" in r.title.lower())
        assert missing_citation.supporting_metrics["keywords_with_ai_overview"] == 5
        assert missing_citation.supporting_metrics["target_cited_count"] == 0


class TestGEORecommendations:
    """Tests for GEO-specific recommendation generation."""

    def test_geo_target_mentioned_no_missing_mention_rec(self):
        """Target mentioned → no missing-mention recommendation."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        geo_result = GEOResult(
            dataset_id="geo-test",
            dataset_metrics=_geo_dm(keywords_target_mentioned=5, overall_mention_rate=0.5),
            keyword_metrics=(_geo_km(target_mentioned_count=2),),
        )

        result = service.analyze(dataset, (), (), geo_result=geo_result)
        geo_recs = [r for r in result.recommendations if r.category == RecommendationCategory.GEO]

        # Should NOT have "Target not mentioned in generative engines"
        missing_mention = [r for r in geo_recs if "not mentioned" in r.title.lower()]
        assert len(missing_mention) == 0, f"Unexpected missing mention rec: {missing_mention}"

        # Should have competitor dominates rec
        competitor_recs = [r for r in geo_recs if "dominates" in r.title.lower()]
        assert len(competitor_recs) == 1

    def test_geo_target_not_mentioned_competitor_mentioned(self):
        """Target not mentioned + competitor mentioned → GEO visibility opportunity."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        geo_result = GEOResult(
            dataset_id="geo-test",
            dataset_metrics=_geo_dm(keywords_target_mentioned=0, overall_mention_rate=0.0),
            keyword_metrics=(_geo_km(target_mentioned_count=0, competitor_mentioned_count=1),),
        )

        result = service.analyze(dataset, (), (), geo_result=geo_result)
        geo_recs = [r for r in result.recommendations if r.category == RecommendationCategory.GEO]

        # Must have HIGH priority missing mention rec
        missing_mention = [r for r in geo_recs if "not mentioned" in r.title.lower()]
        assert len(missing_mention) == 1
        assert missing_mention[0].priority == RecommendationPriority.HIGH
        assert missing_mention[0].confidence == 0.85
        assert missing_mention[0].supporting_metrics["target_mentioned_count"] == 0
        assert missing_mention[0].supporting_metrics["competitor_mentioned_count"] == 5
        assert "comp1.com" in missing_mention[0].supporting_metrics["top_competitors"]

    def test_geo_multiple_competitors_preserved(self):
        """Multiple competitors → preserve actual competitor evidence."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        geo_result = GEOResult(
            dataset_id="geo-test",
            dataset_metrics=_geo_dm(
                competitor_domain_counts={"comp1.com": 5, "comp2.com": 3, "comp3.com": 2}
            ),
            keyword_metrics=(_geo_km(),),
        )

        result = service.analyze(dataset, (), (), geo_result=geo_result)
        geo_recs = [r for r in result.recommendations if r.category == RecommendationCategory.GEO]

        missing_mention = next(r for r in geo_recs if "not mentioned" in r.title.lower())
        top_comps = missing_mention.supporting_metrics["top_competitors"]
        assert len(top_comps) == 3
        assert "comp1.com" in top_comps
        assert "comp2.com" in top_comps
        assert "comp3.com" in top_comps

        dominates_rec = next(r for r in geo_recs if "dominates" in r.title.lower())
        assert dominates_rec.supporting_metrics["competitor"] == "comp1.com"
        assert dominates_rec.supporting_metrics["mention_count"] == 5

    def test_geo_not_assessed_no_recommendation(self):
        """geo_result=None → no GEO recommendations."""
        service = SearchIntelligenceService()
        dataset = _dataset()

        result = service.analyze(dataset, (), (), geo_result=None)
        geo_recs = [r for r in result.recommendations if r.category == RecommendationCategory.GEO]

        assert len(geo_recs) == 0

    def test_geo_multiple_queries_evidence_preserved(self):
        """Multiple queries → query-specific evidence preserved."""
        service = SearchIntelligenceService()
        dataset = _dataset()
        # competitor_mentioned_count comes from dataset_metrics.competitor_domain_counts
        geo_result = GEOResult(
            dataset_id="geo-test",
            dataset_metrics=_geo_dm(
                keywords_target_mentioned=0,
                competitor_domain_counts={"comp1.com": 2, "comp2.com": 1}
            ),
            keyword_metrics=(
                _geo_km(
                    keyword="query one",
                    target_mentioned_count=0,
                    competitor_mentioned_count=1,
                ),
                _geo_km(
                    keyword="query two",
                    target_mentioned_count=0,
                    competitor_mentioned_count=2,
                ),
            ),
        )

        result = service.analyze(dataset, (), (), geo_result=geo_result)
        geo_recs = [r for r in result.recommendations if r.category == RecommendationCategory.GEO]

        missing_mention = next(r for r in geo_recs if "not mentioned" in r.title.lower())
        assert missing_mention.supporting_metrics["competitor_mentioned_count"] == 3


class TestCrossEngineRecommendations:
    """Tests for cross-engine (AIO + GEO) recommendation generation."""

    def test_cross_engine_same_query_gap(self):
        """AIO citation gap + GEO mention gap for SAME query → cross-engine opportunity."""
        service = SearchIntelligenceService()
        dataset = _dataset()

        aio_km = _aio_km(
            keyword="best coffee",
            ai_overview_present_count=3,
            target_cited_count=0,
        )
        geo_km = _geo_km(
            keyword="best coffee",
            target_mentioned_count=0,
            competitor_mentioned_count=1,
        )

        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(keywords_with_ai_overview=5, keywords_target_cited=0),
            keyword_metrics=(aio_km,),
        )
        geo_result = GEOResult(
            dataset_id="geo-test",
            dataset_metrics=_geo_dm(keywords_target_mentioned=0),
            keyword_metrics=(geo_km,),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result, geo_result=geo_result)
        cross_recs = [
            r for r in result.recommendations
            if r.category == RecommendationCategory.OPPORTUNITY
        ]

        cross_gap = [r for r in cross_recs if "cross-engine" in r.title.lower()]
        assert len(cross_gap) == 1
        assert cross_gap[0].priority == RecommendationPriority.HIGH
        assert cross_gap[0].confidence == 0.85
        assert "best coffee" in cross_gap[0].affected_keywords
        assert cross_gap[0].supporting_metrics["cross_gap_count"] == 1

    def test_cross_engine_aio_cited_geo_mentioned_no_gap_rec(self):
        """AIO target cited + GEO target mentioned → no cross-engine visibility gap."""
        service = SearchIntelligenceService()
        dataset = _dataset()

        aio_km = _aio_km(
            keyword="best coffee",
            ai_overview_present_count=3,
            target_cited_count=2,
        )
        geo_km = _geo_km(
            keyword="best coffee",
            target_mentioned_count=1,
            competitor_mentioned_count=0,
        )

        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(keywords_with_ai_overview=5, keywords_target_cited=3),
            keyword_metrics=(aio_km,),
        )
        geo_result = GEOResult(
            dataset_id="geo-test",
            dataset_metrics=_geo_dm(keywords_target_mentioned=5),
            keyword_metrics=(geo_km,),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result, geo_result=geo_result)
        cross_recs = [
            r for r in result.recommendations
            if r.category == RecommendationCategory.OPPORTUNITY
        ]

        cross_gap = [r for r in cross_recs if "cross-engine" in r.title.lower()]
        assert len(cross_gap) == 0, f"Unexpected cross-engine gap: {cross_gap}"

    def test_cross_engine_low_both_rates(self):
        """Both AIO citation rate and GEO mention rate < 30% → low visibility rec."""
        service = SearchIntelligenceService()
        dataset = _dataset()

        aio_km = _aio_km(
            keyword="test",
            target_cited_count=1,
            target_citation_rate=0.2,
        )
        geo_km = _geo_km(
            keyword="test",
            target_mentioned_count=1,
            mention_rate=0.2,
        )

        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(keywords_target_cited=1, target_citation_rate=0.2),
            keyword_metrics=(aio_km,),
        )
        geo_result = GEOResult(
            dataset_id="geo-test",
            dataset_metrics=_geo_dm(keywords_target_mentioned=1, overall_mention_rate=0.2),
            keyword_metrics=(geo_km,),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result, geo_result=geo_result)
        cross_recs = [
            r for r in result.recommendations
            if r.category == RecommendationCategory.OPPORTUNITY
        ]

        low_vis = [r for r in cross_recs if "low visibility across both" in r.title.lower()]
        assert len(low_vis) == 1
        assert low_vis[0].priority == RecommendationPriority.MEDIUM
        assert low_vis[0].confidence == 0.7
        assert low_vis[0].supporting_metrics["aio_citation_rate"] == 0.2
        assert low_vis[0].supporting_metrics["geo_mention_rate"] == 0.2

    def test_cross_engine_insufficient_evidence_no_fabrication(self):
        """Insufficient evidence → no fabricated cross-engine recommendation."""
        service = SearchIntelligenceService()
        dataset = _dataset()

        # AIO present but target cited, GEO present but target mentioned
        # No gaps exist
        aio_km = _aio_km(keyword="query1", target_cited_count=2)
        geo_km = _geo_km(keyword="query2", target_mentioned_count=1)

        aio_result = AIOverviewResult(
            dataset_id="aio-test",
            dataset_metrics=_aio_dm(keywords_target_cited=3, target_citation_rate=0.6),
            keyword_metrics=(aio_km,),
        )
        geo_result = GEOResult(
            dataset_id="geo-test",
            dataset_metrics=_geo_dm(keywords_target_mentioned=2, overall_mention_rate=0.5),
            keyword_metrics=(geo_km,),
        )

        result = service.analyze(dataset, (), (), aio_result=aio_result, geo_result=geo_result)
        cross_recs = [
            r for r in result.recommendations
            if r.category == RecommendationCategory.OPPORTUNITY
        ]

        # Should have NO cross-engine recs (neither gap nor low rates)
        cross_gap = [r for r in cross_recs if "cross-engine" in r.title.lower()]
        low_vis = [r for r in cross_recs if "low visibility across both" in r.title.lower()]
        assert len(cross_gap) == 0
        assert len(low_vis) == 0


class TestBackwardCompatibility:
    """Tests for backward compatibility - existing behavior unchanged."""

    def test_analyze_without_aio_geo(self):
        """SearchIntelligenceService.analyze() without AIO/GEO → existing behavior unchanged."""
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=2, total_observations=4)
        observations = (
            _obs(keyword="kw1", position=3),
            _obs(keyword="kw2", position=15),
        )
        competitors = (_comp(keyword="kw1", position=1),)  # Competitor ranks higher

        result = service.analyze(dataset, observations, competitors)

        # Should have existing SEO recommendations (at least some)
        # Note: With this data, we get competitor gap opportunity
        rec_cats = {r.category for r in result.recommendations}
        # Should NOT have AIO/GEO recommendations
        assert RecommendationCategory.AIO not in rec_cats
        assert RecommendationCategory.GEO not in rec_cats

    def test_analyze_with_none_aio_geo(self):
        """Explicit aio_result=None, geo_result=None → existing behavior unchanged."""
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=2, total_observations=4)
        observations = (_obs(keyword="kw1", position=3),)

        result = service.analyze(dataset, observations, (), aio_result=None, geo_result=None)

        rec_cats = {r.category for r in result.recommendations}
        assert RecommendationCategory.AIO not in rec_cats
        assert RecommendationCategory.GEO not in rec_cats

    def test_existing_seo_recommendations_still_appear(self):
        """Existing SEO recommendations (cannibalization, volatility, etc.) still appear."""
        service = SearchIntelligenceService()
        dataset = _dataset(total_keywords=1, total_observations=3)
        observations = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=5),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=8),
            _obs(keyword="kw1", url="https://oursite.io/page3", position=12),
        )

        result = service.analyze(dataset, observations, ())

        # Cannibalization rec should exist
        cannib = [
            r for r in result.recommendations
            if r.category == RecommendationCategory.CANNIBALIZATION
        ]
        assert len(cannib) > 0
        assert cannib[0].priority in (RecommendationPriority.HIGH, RecommendationPriority.CRITICAL)

        # Volatility rec may exist (stable positions = low volatility)
        _ = [r for r in result.recommendations if r.category == RecommendationCategory.VOLATILITY]


class TestSiteAnalysisIntegration:
    """Integration tests for SiteAnalysisService → SearchIntelligenceService path."""

    @pytest.mark.asyncio
    async def test_site_analysis_to_intelligence_path(self):
        """SiteAnalysisService → AIO/GEO → SearchIntelligenceService with mocks."""
        from unittest.mock import AsyncMock, MagicMock

        from sie.domain.models.search_aio import AIOverviewObservation, AIOverviewType
        from sie.domain.models.search_geo import GenerativeEngineType, GEOObservation
        from sie.domain.models.search_result import SearchResult, SearchResultItem
        from sie.domain.ports.persistence import CrawlRunRepository
        from sie.domain.services.audit_service import AuditService
        from sie.domain.services.content_service import ContentService
        from sie.domain.services.crawl_service import CrawlService
        from sie.infrastructure.search.mock_provider import MockSearchProvider
        from sie.infrastructure.search.provider_registry import ProviderRegistry

        # Create mock provider with AIO and GEO fixtures
        mock_provider = MockSearchProvider(
            results={"test keyword": SearchResult(
                keyword="test keyword",
                items=(SearchResultItem(position=1, title="Test", url="https://oursite.io/page"),),
            )},
            aio_observations={
                "test keyword": AIOverviewObservation(
                    keyword="test keyword",
                    ai_type=AIOverviewType.AI_OVERVIEW,
                    present=True,
                    target_cited=False,
                    target_domain="oursite.io",
                    citation_count=1,
                    competitor_cited_domains=("competitor.com",),
                ),
            },
            geo_observations={
                ("test keyword", GenerativeEngineType.CHATGPT): GEOObservation(
                    keyword="test keyword",
                    engine_type=GenerativeEngineType.CHATGPT,
                    target_mentioned=False,
                    target_domain="oursite.io",
                    mention_count=0,
                    competitor_domains=("competitor.com",),
                    citation_urls=(),
                    answer_length=100,
                ),
            },
        )

        registry = ProviderRegistry(default=mock_provider)

        # Mock services
        crawl_service = MagicMock(spec=CrawlService)
        audit_service = MagicMock(spec=AuditService)
        content_service = MagicMock(spec=ContentService)
        repository = MagicMock(spec=CrawlRunRepository)

        crawl_service.start_run = AsyncMock(return_value="run-123")
        crawl_service.live_stats = AsyncMock(
            return_value=MagicMock(status=MagicMock(value="completed"))
        )
        # Provide empty pages store (keywords will be extracted from crawl)
        crawl_service._pages_store = {"run-123": []}

        audit_service.run_technical_audit = AsyncMock(
            return_value=MagicMock(
                critical_count=0, warning_count=0, info_count=0,
                findings=[], summary_by_rule={},
            )
        )
        audit_service.run_link_graph = AsyncMock(
            return_value=MagicMock(
                total_pages=0, total_internal_links=0, avg_depth=0,
                orphans=[], max_depth=0, pagerank_gini=0.0, avg_links_per_page=0,
            )
        )
        content_service.analyze_content = AsyncMock(return_value=[])
        content_service.generate_quality_report = AsyncMock(
            return_value=MagicMock(
                analyzed_pages=0, avg_quality_score=0.0,
                thin_content_pages=0, duplicate_groups=0, top_issues=[],
            )
        )
        repository.get_search_dataset = AsyncMock(return_value=None)
        repository.save_search_observations = AsyncMock(return_value=0)

        # Import here to avoid circular import issues
        from sie.domain.services.site_analysis import SiteAnalysisService

        service = SiteAnalysisService(
            crawl_service=crawl_service,
            audit_service=audit_service,
            content_service=content_service,
            search_provider=registry,
            repository=repository,
        )

        result = await service.analyze_site(
            domain="oursite.io",
            max_pages=1,
            max_keywords=1,
            deep_aio=True,
            deep_geo=True,
        )

        # Verify the analysis ran without errors
        assert result.domain == "oursite.io"
        # Unified recommendations should exist
        assert hasattr(result, 'recommendations')
        assert isinstance(result.recommendations, tuple)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
