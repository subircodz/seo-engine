"""Unit tests for AIO (AI Overview) intelligence (Phase 6N-F)."""

from datetime import UTC, datetime

import pytest

from sie.domain.engines.search_aio import (
    analyze_aio_observations,
    calculate_aio_dataset_metrics,
    calculate_aio_keyword_metrics,
)
from sie.domain.models.search_aio import (
    AIOCitation,
    AIOverviewObservation,
    AIOverviewResult,
    AIOverviewType,
    CitationSource,
)

_T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def _obs(
    keyword="seo tools",
    ai_type=AIOverviewType.AI_OVERVIEW,
    present=True,
    target_cited=False,
    target_domain="oursite.io",
    citation_count=0,
    citations=(),
    competitor_cited_domains=(),
    observed_at=_T0,
    source="manual",
):
    return AIOverviewObservation(
        keyword=keyword,
        ai_type=ai_type,
        present=present,
        target_cited=target_cited,
        target_domain=target_domain,
        citation_count=citation_count,
        citations=citations,
        competitor_cited_domains=competitor_cited_domains,
        observed_at=observed_at,
        source=source,
    )


# ── Model tests ─────────────────────────────────────────────────────────


class TestAIOverviewType:
    def test_all_members_present(self):
        assert AIOverviewType.AI_OVERVIEW.value == "ai_overview"
        assert AIOverviewType.COPILOT.value == "copilot"
        assert AIOverviewType.PERPLEXITY.value == "perplexity"
        assert AIOverviewType.CHATGPT_SEARCH.value == "chatgpt_search"
        assert AIOverviewType.OTHER.value == "other"

    def test_is_str_enum(self):
        assert issubclass(AIOverviewType, str)


class TestCitationSource:
    def test_all_members_present(self):
        assert CitationSource.WEB_PAGE.value == "web_page"
        assert CitationSource.KNOWLEDGE_GRAPH.value == "knowledge_graph"
        assert CitationSource.NEWS.value == "news"
        assert CitationSource.VIDEO.value == "video"
        assert CitationSource.OTHER.value == "other"


class TestAIOCitation:
    def test_valid_citation(self):
        c = AIOCitation(domain="example.com", url="https://example.com/page")
        assert c.domain == "example.com"
        assert c.url == "https://example.com/page"
        assert c.position == 0
        assert c.source_type == CitationSource.WEB_PAGE

    def test_domain_casefolded(self):
        c = AIOCitation(domain="Example.COM")
        assert c.domain == "example.com"

    def test_domain_www_stripped(self):
        c = AIOCitation(domain="www.example.com")
        assert c.domain == "example.com"

    def test_empty_domain_rejected(self):
        with pytest.raises(ValueError, match="domain"):
            AIOCitation(domain="")

    def test_whitespace_domain_rejected(self):
        with pytest.raises(ValueError, match="domain"):
            AIOCitation(domain="   ")


class TestAIOverviewObservation:
    def test_valid_observation(self):
        o = _obs()
        assert o.keyword == "seo tools"
        assert o.present is True
        assert o.target_cited is False

    def test_keyword_casefolded(self):
        o = _obs(keyword="SEO Tools")
        assert o.keyword == "seo tools"

    def test_keyword_whitespace_normalised(self):
        o = _obs(keyword="  seo   tools  ")
        assert o.keyword == "seo tools"

    def test_target_domain_casefolded(self):
        o = _obs(target_domain="Example.IO")
        assert o.target_domain == "example.io"

    def test_empty_keyword_rejected(self):
        with pytest.raises(ValueError, match="keyword"):
            AIOverviewObservation(keyword="", ai_type=AIOverviewType.AI_OVERVIEW, present=True)


# ── Analytics tests ─────────────────────────────────────────────────────


class TestAIOverviewKeywordMetrics:
    def test_no_observations(self):
        metrics = calculate_aio_keyword_metrics(())
        assert metrics == []

    def test_single_observation(self):
        observations = (_obs(present=True, target_cited=True),)
        metrics = calculate_aio_keyword_metrics(observations)
        assert len(metrics) == 1
        m = metrics[0]
        assert m.keyword == "seo tools"
        assert m.observation_count == 1
        assert m.ai_overview_present_count == 1
        assert m.target_cited_count == 1
        assert m.citation_rate == 1.0
        assert m.target_citation_rate == 1.0

    def test_mixed_observations(self):
        observations = (
            _obs(present=True, target_cited=True),
            _obs(present=True, target_cited=False, observed_at=_T1),
            _obs(present=False, observed_at=_T1),
        )
        metrics = calculate_aio_keyword_metrics(observations)
        assert len(metrics) == 1
        m = metrics[0]
        assert m.observation_count == 3
        assert m.ai_overview_present_count == 2
        assert m.target_cited_count == 1
        assert m.citation_rate == pytest.approx(0.6667, abs=0.001)
        assert m.target_citation_rate == pytest.approx(0.5, abs=0.001)

    def test_no_ai_overview(self):
        observations = (
            _obs(present=False),
            _obs(present=False, observed_at=_T1),
        )
        metrics = calculate_aio_keyword_metrics(observations)
        m = metrics[0]
        assert m.ai_overview_present_count == 0
        assert m.citation_rate == 0.0
        assert m.target_citation_rate == 0.0

    def test_multiple_keywords_sorted(self):
        observations = (
            _obs(keyword="beta"),
            _obs(keyword="alpha"),
            _obs(keyword="gamma"),
        )
        metrics = calculate_aio_keyword_metrics(observations)
        keywords = [m.keyword for m in metrics]
        assert keywords == ["alpha", "beta", "gamma"]


class TestAIOverviewDatasetMetrics:
    def test_empty_observations(self):
        dm = calculate_aio_dataset_metrics("ds-1", (), 10)
        assert dm.total_keywords == 10
        assert dm.keywords_with_ai_overview == 0
        assert dm.target_citation_rate == 0.0

    def test_with_observations(self):
        observations = (
            _obs(present=True, target_cited=True, competitor_cited_domains=("comp1.com",)),
            _obs(
                present=True,
                target_cited=False,
                competitor_cited_domains=("comp2.com",),
                observed_at=_T1,
            ),
            _obs(present=False, observed_at=_T1),
        )
        dm = calculate_aio_dataset_metrics("ds-1", observations, 5)
        assert dm.total_keywords == 5
        assert dm.keywords_with_ai_overview == 1
        assert dm.keywords_target_cited == 1
        assert dm.total_ai_overview_observations == 2
        assert dm.total_citations == 1
        assert dm.target_citation_rate == 1.0
        assert "comp1.com" in dm.competitor_cited_domains
        assert "comp2.com" in dm.competitor_cited_domains

    def test_no_ai_overviews(self):
        observations = (_obs(present=False),)
        dm = calculate_aio_dataset_metrics("ds-1", observations, 3)
        assert dm.keywords_with_ai_overview == 0
        assert dm.target_citation_rate == 0.0


class TestAnalyzeAIO:
    def test_full_analysis(self):
        observations = (
            _obs(present=True, target_cited=True),
            _obs(present=True, target_cited=False, observed_at=_T1),
        )
        result = analyze_aio_observations("ds-1", observations, 5)
        assert isinstance(result, AIOverviewResult)
        assert result.dataset_id == "ds-1"
        assert len(result.keyword_metrics) == 1
        assert result.dataset_metrics.total_keywords == 5
