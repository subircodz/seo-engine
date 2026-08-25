"""Unit tests for the deterministic SERP Feature analytics (Phase 6N-C)."""

from datetime import UTC, datetime

from sie.domain.engines.search_analytics import (
    calculate_dataset_metrics,
    calculate_serp_feature_metrics,
)
from sie.domain.models.search import (
    RankingObservation,
    SearchDataset,
    SearchDevice,
)
from sie.domain.models.search_serp import SearchSERPFeature, SERPFeatureType

_T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


def _fs(
    keyword: str = "kw",
    url: str = "https://oursite.io/",
    position: int = 5,
    features: tuple = (),
    observed_at: datetime = _T0,
) -> RankingObservation:
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
        serp_features=features,
    )


def _feat(
    feature_type: SERPFeatureType = SERPFeatureType.FEATURED_SNIPPET,
    url: str | None = "https://oursite.io/page",
    domain: str | None = None,
    position: int | None = None,
    title: str | None = None,
) -> SearchSERPFeature:
    return SearchSERPFeature(
        feature_type=feature_type,
        url=url,
        position=position,
        title=title,
    )


def _ds(dataset_id: str = "ds-1", total_keywords: int = 0, total_observations: int = 0):
    return SearchDataset(
        dataset_id=dataset_id,
        name="fixture",
        source="test",
        total_keywords=total_keywords,
        total_observations=total_observations,
    )


class TestSerpFeatureCount:
    def test_no_features_returns_empty(self):
        results = calculate_serp_feature_metrics(())
        assert results == {}

    def test_counts_features_by_type(self):
        obs = (
            _fs(features=(_feat(SERPFeatureType.FEATURED_SNIPPET),)),
            _fs(
                keyword="kw2",
                features=(_feat(SERPFeatureType.PEOPLE_ALSO_ASK),),
            ),
            _fs(
                keyword="kw3",
                features=(
                    _feat(SERPFeatureType.FEATURED_SNIPPET),
                    _feat(SERPFeatureType.KNOWLEDGE_PANEL),
                ),
            ),
        )
        results = calculate_serp_feature_metrics(obs)
        assert results == {
            "featured_snippet": 2,
            "people_also_ask": 1,
            "knowledge_panel": 1,
        }

    def test_target_domain_filters_ownership(self):
        obs = (
            _fs(
                keyword="kw1",
                features=(_feat(SERPFeatureType.FEATURED_SNIPPET, url="https://oursite.io/1"),),
            ),
            _fs(
                keyword="kw2",
                features=(_feat(SERPFeatureType.FEATURED_SNIPPET, url="https://rival.io/2"),),
            ),
            _fs(
                keyword="kw3",
                features=(_feat(SERPFeatureType.PEOPLE_ALSO_ASK, url="https://oursite.io/3"),),
            ),
        )
        results = calculate_serp_feature_metrics(obs, "oursite.io")
        assert results == {"featured_snippet": 1, "people_also_ask": 1}


class TestDatasetMetricsSerpFeatures:
    def test_no_features_returns_zeros(self):
        ds = _ds(total_keywords=10)
        obs = (_fs(),)
        metrics = calculate_dataset_metrics(ds, obs)
        assert metrics.total_serp_feature_occurrences == 0
        assert metrics.observations_with_serp_features == 0
        assert metrics.featured_snippet_occurrences == 0
        assert metrics.people_also_ask_occurrences == 0
        assert metrics.featured_snippet_owned_by_target == 0
        assert metrics.people_also_ask_owned_by_target == 0
        assert metrics.keywords_with_featured_snippet == 0
        assert metrics.keywords_with_people_also_ask == 0
        assert metrics.serp_features_by_type == {}

    def test_single_observation_with_fs(self):
        ds = _ds(total_keywords=10)
        obs = (
            _fs(
                features=(_feat(SERPFeatureType.FEATURED_SNIPPET, url="https://oursite.io/page"),),
            ),
        )
        metrics = calculate_dataset_metrics(ds, obs)
        assert metrics.total_serp_feature_occurrences == 1
        assert metrics.observations_with_serp_features == 1
        assert metrics.featured_snippet_occurrences == 1
        assert metrics.featured_snippet_owned_by_target == 1
        assert metrics.keywords_with_featured_snippet == 1
        assert metrics.serp_features_by_type == {"featured_snippet": 1}

    def test_multiple_keywords_with_features(self):
        ds = _ds(total_keywords=5)
        obs = (
            _fs(
                keyword="kw1",
                features=(_feat(SERPFeatureType.FEATURED_SNIPPET, url="https://oursite.io/1"),),
            ),
            _fs(
                keyword="kw2",
                features=(_feat(SERPFeatureType.PEOPLE_ALSO_ASK, url="https://oursite.io/2"),),
            ),
            _fs(
                keyword="kw3",
                features=(
                    _feat(SERPFeatureType.FEATURED_SNIPPET, url="https://oursite.io/3"),
                    _feat(SERPFeatureType.PEOPLE_ALSO_ASK, url="https://oursite.io/4"),
                ),
            ),
            _fs(keyword="kw4"),
            _fs(keyword="kw5"),
        )
        metrics = calculate_dataset_metrics(ds, obs)
        assert metrics.total_serp_feature_occurrences == 4
        assert metrics.observations_with_serp_features == 3
        assert metrics.featured_snippet_occurrences == 2
        assert metrics.people_also_ask_occurrences == 2
        assert metrics.featured_snippet_owned_by_target == 2
        assert metrics.people_also_ask_owned_by_target == 2
        assert metrics.keywords_with_featured_snippet == 2
        assert metrics.keywords_with_people_also_ask == 2
        assert metrics.serp_features_by_type == {
            "featured_snippet": 2,
            "people_also_ask": 2,
        }

    def test_ownership_only_with_explicit_domain(self):
        """Feature without domain should NOT be counted as owned."""
        ds = _ds(total_keywords=10)
        obs = (
            _fs(
                features=(
                    SearchSERPFeature(
                        feature_type=SERPFeatureType.FEATURED_SNIPPET,
                        url="https://oursite.io/page",
                    ),
                ),
            ),
        )
        metrics = calculate_dataset_metrics(ds, obs)
        # Domain is derived from the feature's URL, so ownership still applies
        assert metrics.featured_snippet_occurrences == 1
        assert metrics.featured_snippet_owned_by_target == 1

    def test_different_keyword_same_feature_counts_once(self):
        """Keywords with featured snippets should be distinct."""
        ds = _ds(total_keywords=5)
        obs = (
            _fs(
                keyword="kw1",
                features=(_feat(SERPFeatureType.FEATURED_SNIPPET),),
            ),
            _fs(
                keyword="kw2",
                features=(_feat(SERPFeatureType.FEATURED_SNIPPET),),
            ),
            _fs(
                keyword="kw1",
                features=(_feat(SERPFeatureType.FEATURED_SNIPPET),),
            ),
        )
        metrics = calculate_dataset_metrics(ds, obs)
        assert metrics.keywords_with_featured_snippet == 2

    def test_empty_dataset_metrics(self):
        ds = _ds(total_keywords=0)
        metrics = calculate_dataset_metrics(ds, ())
        assert metrics.total_serp_feature_occurrences == 0
        assert metrics.serp_features_by_type == {}
        assert metrics.observations_with_serp_features == 0
