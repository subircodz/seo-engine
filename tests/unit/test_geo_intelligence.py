"""Unit tests for GEO (Generative Engine Optimization) intelligence (Phase 6N-G)."""

from datetime import UTC, datetime

import pytest

from sie.domain.engines.search_geo import (
    analyze_geo_observations,
    calculate_geo_dataset_metrics,
    calculate_geo_keyword_metrics,
)
from sie.domain.models.search_geo import (
    EntityMention,
    EntityType,
    GenerativeEngineType,
    GEOObservation,
    GEOResult,
)

_T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def _obs(
    keyword="best seo tools",
    engine_type=GenerativeEngineType.PERPLEXITY,
    target_mentioned=False,
    target_domain="oursite.io",
    mention_count=0,
    entity_mentions=(),
    competitor_domains=(),
    citation_urls=(),
    observed_at=_T0,
    source="manual",
):
    return GEOObservation(
        keyword=keyword,
        engine_type=engine_type,
        target_mentioned=target_mentioned,
        target_domain=target_domain,
        mention_count=mention_count,
        entity_mentions=entity_mentions,
        competitor_domains=competitor_domains,
        citation_urls=citation_urls,
        observed_at=observed_at,
        source=source,
    )


# ── Model tests ─────────────────────────────────────────────────────────


class TestGenerativeEngineType:
    def test_all_members_present(self):
        assert GenerativeEngineType.GOOGLE_AI_OVERVIEW.value == "google_ai_overview"
        assert GenerativeEngineType.BING_COPILOT.value == "bing_copilot"
        assert GenerativeEngineType.PERPLEXITY.value == "perplexity"
        assert GenerativeEngineType.CHATGPT.value == "chatgpt"
        assert GenerativeEngineType.CLAUDE.value == "claude"
        assert GenerativeEngineType.GEMINI.value == "gemini"
        assert GenerativeEngineType.OTHER.value == "other"

    def test_is_str_enum(self):
        assert issubclass(GenerativeEngineType, str)


class TestEntityType:
    def test_all_members_present(self):
        assert EntityType.BRAND.value == "brand"
        assert EntityType.PRODUCT.value == "product"
        assert EntityType.PERSON.value == "person"
        assert EntityType.LOCATION.value == "location"
        assert EntityType.ORGANIZATION.value == "organization"
        assert EntityType.OTHER.value == "other"


class TestEntityMention:
    def test_valid_mention(self):
        m = EntityMention(text="Acme Corp", entity_type=EntityType.BRAND, is_target=True)
        assert m.text == "Acme Corp"
        assert m.entity_type == EntityType.BRAND
        assert m.is_target is True

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError, match="text"):
            EntityMention(text="")


class TestGEOObservation:
    def test_valid_observation(self):
        o = _obs()
        assert o.keyword == "best seo tools"
        assert o.target_mentioned is False

    def test_keyword_casefolded(self):
        o = _obs(keyword="Best SEO Tools")
        assert o.keyword == "best seo tools"

    def test_keyword_whitespace_normalised(self):
        o = _obs(keyword="  best   seo   tools  ")
        assert o.keyword == "best seo tools"

    def test_target_domain_casefolded(self):
        o = _obs(target_domain="Example.IO")
        assert o.target_domain == "example.io"

    def test_empty_keyword_rejected(self):
        with pytest.raises(ValueError, match="keyword"):
            GEOObservation(
                keyword="",
                engine_type=GenerativeEngineType.PERPLEXITY,
                target_mentioned=False,
            )


# ── Analytics tests ─────────────────────────────────────────────────────


class TestGEOKwordMetrics:
    def test_no_observations(self):
        metrics = calculate_geo_keyword_metrics(())
        assert metrics == []

    def test_single_observation(self):
        observations = (_obs(target_mentioned=True, mention_count=2),)
        metrics = calculate_geo_keyword_metrics(observations)
        assert len(metrics) == 1
        m = metrics[0]
        assert m.keyword == "best seo tools"
        assert m.observation_count == 1
        assert m.target_mentioned_count == 1
        assert m.mention_rate == 1.0
        assert m.avg_mention_count == 2.0

    def test_mixed_observations(self):
        observations = (
            _obs(target_mentioned=True, mention_count=3),
            _obs(target_mentioned=False, observed_at=_T1),
            _obs(target_mentioned=True, mention_count=1, observed_at=_T1),
        )
        metrics = calculate_geo_keyword_metrics(observations)
        m = metrics[0]
        assert m.observation_count == 3
        assert m.target_mentioned_count == 2
        assert m.mention_rate == pytest.approx(0.6667, abs=0.001)
        assert m.avg_mention_count == 2.0

    def test_multiple_keywords_sorted(self):
        observations = (
            _obs(keyword="beta"),
            _obs(keyword="alpha"),
            _obs(keyword="gamma"),
        )
        metrics = calculate_geo_keyword_metrics(observations)
        keywords = [m.keyword for m in metrics]
        assert keywords == ["alpha", "beta", "gamma"]


class TestGEODatasetMetrics:
    def test_empty_observations(self):
        dm = calculate_geo_dataset_metrics("ds-1", (), 10)
        assert dm.total_keywords == 10
        assert dm.keywords_target_mentioned == 0
        assert dm.overall_mention_rate == 0.0

    def test_with_observations(self):
        observations = (
            _obs(target_mentioned=True, competitor_domains=("comp1.com",)),
            _obs(target_mentioned=True, competitor_domains=("comp2.com",), observed_at=_T1),
            _obs(target_mentioned=False, observed_at=_T1),
        )
        dm = calculate_geo_dataset_metrics("ds-1", observations, 5)
        assert dm.total_keywords == 5
        assert dm.keywords_target_mentioned == 1
        assert dm.total_observations == 3
        assert dm.total_target_mentions == 2
        assert dm.overall_mention_rate == pytest.approx(0.2, abs=0.001)
        assert dm.competitor_domain_counts.get("comp1.com") == 1
        assert dm.competitor_domain_counts.get("comp2.com") == 1

    def test_no_mentions(self):
        observations = (_obs(target_mentioned=False),)
        dm = calculate_geo_dataset_metrics("ds-1", observations, 3)
        assert dm.keywords_target_mentioned == 0
        assert dm.overall_mention_rate == 0.0


class TestAnalyzeGEO:
    def test_full_analysis(self):
        observations = (
            _obs(target_mentioned=True, mention_count=2),
            _obs(target_mentioned=False, observed_at=_T1),
        )
        result = analyze_geo_observations("ds-1", observations, 5)
        assert isinstance(result, GEOResult)
        assert result.dataset_id == "ds-1"
        assert len(result.keyword_metrics) == 1
        assert result.dataset_metrics.total_keywords == 5
