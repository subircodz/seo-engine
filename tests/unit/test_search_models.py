"""Unit tests for Search Intelligence domain models (Phase 6A)."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
    SearchIntent,
    SearchKeyword,
    SearchQuery,
)

# ════════════════════════════════════════════════════════════════════════════
# SearchKeyword
# ════════════════════════════════════════════════════════════════════════════


class TestSearchKeyword:
    def test_valid_keyword_defaults(self):
        kw = SearchKeyword(keyword="best running shoes")
        assert kw.keyword == "best running shoes"
        assert kw.normalized_keyword == "best running shoes"
        assert kw.search_intent is SearchIntent.UNKNOWN

    def test_keyword_normalization(self):
        kw = SearchKeyword(keyword="  Best   Running\tSHOES  ")
        assert kw.normalized_keyword == "best running shoes"

    def test_explicit_normalized_keyword_overrides_default(self):
        kw = SearchKeyword(keyword="Running Shoes", normalized_keyword="run shoe")
        assert kw.normalized_keyword == "run shoe"

    def test_explicit_intent_preserved(self):
        kw = SearchKeyword(keyword="buy nike pegasus", search_intent=SearchIntent.TRANSACTIONAL)
        assert kw.search_intent is SearchIntent.TRANSACTIONAL

    @pytest.mark.parametrize("bad", ["", "   ", None, 123])
    def test_invalid_keyword_rejected(self, bad):
        with pytest.raises(ValueError, match="keyword"):
            SearchKeyword(keyword=bad)  # type: ignore[arg-type]

    def test_frozen(self):
        kw = SearchKeyword(keyword="seo")
        with pytest.raises(FrozenInstanceError):
            kw.keyword = "changed"  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════════
# RankingObservation
# ════════════════════════════════════════════════════════════════════════════


class TestRankingObservation:
    def test_valid_observation_with_defaults(self):
        obs = RankingObservation(
            keyword="seo tools",
            target_url="https://example.com/tools",
            position=3,
            source="gsc",
        )
        assert obs.search_engine == "google"
        assert obs.country == "us"
        assert obs.language == "en"
        assert obs.device is SearchDevice.DESKTOP
        assert isinstance(obs.observed_at, datetime)
        assert obs.observed_at.tzinfo is UTC

    def test_observation_normalizes_context_fields(self):
        obs = RankingObservation(
            keyword="Seo Tools",
            target_url="https://example.com/tools",
            position=1,
            source="manual",
            search_engine="Bing",
            country="US",
            language="EN",
            device=SearchDevice.MOBILE,
        )
        assert obs.keyword == "seo tools"
        assert obs.search_engine == "bing"
        assert obs.country == "us"
        assert obs.language == "en"

    def test_observation_keeps_provided_timestamp(self):
        ts = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
        obs = RankingObservation(
            keyword="k",
            target_url="https://example.com/",
            position=10,
            source="test",
            observed_at=ts,
        )
        assert obs.observed_at == ts

    @pytest.mark.parametrize("bad_position", [0, -1, -100])
    def test_non_positive_positions_rejected(self, bad_position):
        with pytest.raises(ValueError, match="position"):
            RankingObservation(
                keyword="k", target_url="https://example.com/", position=bad_position, source="s"
            )

    @pytest.mark.parametrize("bad_position", [1.5, "3", True, None])
    def test_non_integer_positions_rejected(self, bad_position):
        with pytest.raises(ValueError, match="position"):
            RankingObservation(
                keyword="k",
                target_url="https://example.com/",
                position=bad_position,
                source="s",  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("bad_url", ["example.com/page", "ftp://example.com/", "", "   "])
    def test_invalid_target_url_rejected(self, bad_url):
        with pytest.raises(ValueError, match="target_url"):
            RankingObservation(keyword="k", target_url=bad_url, position=1, source="s")

    @pytest.mark.parametrize("bad_source", ["", "   ", None])
    def test_missing_source_rejected(self, bad_source):
        with pytest.raises(ValueError, match="source"):
            RankingObservation(
                keyword="k", target_url="https://example.com/", position=1, source=bad_source
            )


# ════════════════════════════════════════════════════════════════════════════
# SearchIntent / SearchDevice
# ════════════════════════════════════════════════════════════════════════════


class TestSearchIntent:
    def test_intent_values(self):
        assert {intent.value for intent in SearchIntent} == {
            "informational",
            "navigational",
            "commercial",
            "transactional",
            "unknown",
        }

    def test_intent_is_string_enum(self):
        assert SearchIntent.INFORMATIONAL == "informational"
        assert str(SearchIntent.COMMERCIAL) == "commercial"


# ════════════════════════════════════════════════════════════════════════════
# SearchQuery
# ════════════════════════════════════════════════════════════════════════════


class TestSearchQuery:
    def test_valid_query_defaults(self):
        q = SearchQuery(query="  Coffee   GRINDER ")
        assert q.query == "coffee grinder"
        assert q.country == "us"
        assert q.language == "en"
        assert q.device is SearchDevice.DESKTOP
        assert q.search_engine == "google"

    def test_empty_query_rejected(self):
        with pytest.raises(ValueError, match="query"):
            SearchQuery(query="   ")


# ════════════════════════════════════════════════════════════════════════════
# SearchDataset
# ════════════════════════════════════════════════════════════════════════════


class TestSearchDataset:
    def test_valid_dataset(self):
        ds = SearchDataset(dataset_id="ds-001", name="Q3 GSC export", source="gsc")
        assert ds.total_keywords == 0
        assert ds.total_observations == 0
        assert isinstance(ds.created_at, datetime)
        assert ds.created_at.tzinfo is UTC

    def test_dataset_counts_preserved_and_normalized(self):
        ds = SearchDataset(
            dataset_id="ds-002",
            name="export",
            source="GSC",
            total_keywords=120,
            total_observations=4567,
        )
        assert ds.source == "GSC"
        assert ds.total_keywords == 120
        assert ds.total_observations == 4567

    @pytest.mark.parametrize("bad_kwargs", [{"dataset_id": ""}, {"name": "  "}, {"source": ""}])
    def test_missing_required_fields_rejected(self, bad_kwargs):
        kwargs = {"dataset_id": "id", "name": "n", "source": "s"} | bad_kwargs
        with pytest.raises(ValueError):
            SearchDataset(**kwargs)

    def test_negative_counts_rejected(self):
        with pytest.raises(ValueError, match="total_keywords"):
            SearchDataset(dataset_id="id", name="n", source="s", total_keywords=-1)
        with pytest.raises(ValueError, match="total_observations"):
            SearchDataset(dataset_id="id", name="n", source="s", total_observations=-5)


# ════════════════════════════════════════════════════════════════════════════
# CompetitorRanking
# ════════════════════════════════════════════════════════════════════════════


class TestCompetitorRanking:
    def test_valid_competitor_ranking(self):
        cr = CompetitorRanking(
            keyword="crm software",
            competitor_domain="RivalCRM.com",
            competitor_url="https://rivalcrm.com/pricing",
            position=2,
        )
        assert cr.competitor_domain == "rivalcrm.com"
        assert cr.position == 2
        assert isinstance(cr.observed_at, datetime)

    def test_domain_strips_www_prefix(self):
        cr = CompetitorRanking(
            keyword="k",
            competitor_domain="www.example.co.uk",
            competitor_url="https://www.example.co.uk/x",
            position=7,
        )
        assert cr.competitor_domain == "example.co.uk"

    @pytest.mark.parametrize(
        ("domain",),
        [
            ("https://rivalcrm.com",),  # scheme not allowed in bare domain
            ("rivalcrm.com/path",),
            ("rival crm.com",),
            ("",),
            ("   ",),
        ],
    )
    def test_invalid_competitor_domain_rejected(self, domain):
        with pytest.raises(ValueError, match="competitor_domain"):
            CompetitorRanking(
                keyword="k", competitor_domain=domain, competitor_url="https://ok.com/", position=1
            )

    def test_invalid_competitor_url_rejected(self):
        with pytest.raises(ValueError, match="competitor_url"):
            CompetitorRanking(
                keyword="k", competitor_domain="rival.com", competitor_url="not-a-url", position=1
            )

    def test_zero_position_rejected(self):
        with pytest.raises(ValueError, match="position"):
            CompetitorRanking(
                keyword="k",
                competitor_domain="rival.com",
                competitor_url="https://rival.com/",
                position=0,
            )


# ════════════════════════════════════════════════════════════════════════════
# Cross-model sanity
# ════════════════════════════════════════════════════════════════════════════


class TestModelInteroperability:
    def test_models_compose_without_fake_data(self):
        kw = SearchKeyword(keyword="Ahrefs alternatives", search_intent=SearchIntent.COMMERCIAL)
        obs = RankingObservation(
            keyword=kw.normalized_keyword,
            target_url="https://oursite.io/blog/alternatives",
            position=4,
            source="unit-test-fixture",
        )
        query = SearchQuery(query=kw.normalized_keyword, device=SearchDevice.TABLET)
        cr = CompetitorRanking(
            keyword=kw.normalized_keyword,
            competitor_domain="competitor.io",
            competitor_url="https://competitor.io/post",
            position=4,
        )
        ds = SearchDataset(dataset_id="ds-x", name="fixtures", source="unit-test-fixture")
        assert obs.keyword == query.query == cr.keyword == kw.normalized_keyword
        assert obs.device is SearchDevice.TABLET or query.device is SearchDevice.TABLET
        assert ds.total_observations == 0

    def test_required_args_are_required(self):
        with pytest.raises(TypeError):
            RankingObservation()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            CompetitorRanking()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            SearchKeyword()  # type: ignore[call-arg]
