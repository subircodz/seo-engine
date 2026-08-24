"""Unit tests for the deterministic Search Analytics Engine (Phase 6G)."""

from datetime import UTC, datetime

import pytest

from sie.domain.engines.search_analytics import (
    analyze_search_dataset,
    calculate_competitor_metrics,
    calculate_dataset_metrics,
    calculate_keyword_metrics,
    calculate_visibility_score,
)
from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
)

_T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)
_T2 = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)


def _obs(
    keyword: str = "kw",
    url: str = "https://oursite.io/",
    position: int = 5,
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
    )


def _comp(
    keyword: str = "kw",
    domain: str = "rival.io",
    position: int = 3,
    url: str | None = None,
    observed_at: datetime = _T0,
) -> CompetitorRanking:
    return CompetitorRanking(
        keyword=keyword,
        competitor_domain=domain,
        competitor_url=url or f"https://{domain}/{keyword.replace(' ', '-')}",
        position=position,
        observed_at=observed_at,
    )


def _ds(dataset_id: str = "ds-1", total_keywords: int = 0, total_observations: int = 0):
    return SearchDataset(
        dataset_id=dataset_id,
        name="fixture",
        source="test",
        total_keywords=total_keywords,
        total_observations=total_observations,
    )


# ── empty input ───────────────────────────────────────────────────────────


class TestEmptyInput:
    def test_empty_keyword_metrics(self):
        assert calculate_keyword_metrics(()) == []

    def test_empty_visibility_score_is_zero(self):
        assert calculate_visibility_score(()) == 0.0

    def test_empty_dataset_metrics(self):
        m = calculate_dataset_metrics(_ds("ds-empty"), ())
        assert m.dataset_id == "ds-empty"
        assert m.total_keywords == 0
        assert m.total_observations == 0
        assert m.keywords_with_rankings == 0
        assert m.keywords_not_ranking == 0
        assert m.average_position is None
        assert m.median_position is None
        assert m.top_3_count == 0
        assert m.top_10_count == 0
        assert m.top_20_count == 0
        assert m.top_50_count == 0
        assert m.visibility_score == 0.0

    def test_empty_competitor_metrics(self):
        assert calculate_competitor_metrics((), ()) == []

    def test_analyze_empty_dataset(self):
        result = analyze_search_dataset(_ds("ds-empty"), (), ())
        assert result.keyword_metrics == ()
        assert result.competitor_metrics == ()
        assert result.dataset_metrics.average_position is None


# ── single keyword ────────────────────────────────────────────────────────


class TestSingleKeyword:
    def test_single_observation_no_trend_inferred(self):
        metrics = calculate_keyword_metrics((_obs(position=4),))
        assert len(metrics) == 1
        k = metrics[0]
        assert k.keyword == "kw"
        assert k.observation_count == 1
        assert k.best_position == 4
        assert k.worst_position == 4
        assert k.first_position == 4
        assert k.latest_position == 4
        assert k.position_change is None
        assert k.improved is False
        assert k.declined is False

    def test_multiple_observations_aggregates(self):
        obs = (_obs(position=8, observed_at=_T0), _obs(position=2, observed_at=_T1))
        k = calculate_keyword_metrics(obs)[0]
        assert k.observation_count == 2
        assert k.best_position == 2
        assert k.worst_position == 8
        assert k.first_position == 8
        assert k.latest_position == 2
        assert k.average_position == 5.0


# ── first / latest & trends ───────────────────────────────────────────────


class TestPositionChange:
    def test_improvement_positive_change(self):
        # started at 9, now at 3 → +6 improvement
        obs = (_obs(position=9, observed_at=_T0), _obs(position=3, observed_at=_T1))
        k = calculate_keyword_metrics(obs)[0]
        assert k.position_change == 6
        assert k.improved is True
        assert k.declined is False

    def test_decline_negative_change(self):
        obs = (_obs(position=2, observed_at=_T0), _obs(position=11, observed_at=_T1))
        k = calculate_keyword_metrics(obs)[0]
        assert k.position_change == -9
        assert k.improved is False
        assert k.declined is True

    def test_unchanged_zero_change(self):
        obs = (_obs(position=5, observed_at=_T0), _obs(position=5, observed_at=_T1))
        k = calculate_keyword_metrics(obs)[0]
        assert k.position_change == 0
        assert k.improved is False
        assert k.declined is False

    def test_first_and_latest_use_observed_at_order_not_input_order(self):
        obs = (_obs(position=10, observed_at=_T2), _obs(position=1, observed_at=_T0))
        k = calculate_keyword_metrics(obs)[0]
        assert k.first_position == 1  # earliest timestamp wins
        assert k.latest_position == 10

    def test_equal_timestamps_keep_input_order(self):
        obs = (_obs(position=7, observed_at=_T0), _obs(position=3, observed_at=_T0))
        k = calculate_keyword_metrics(obs)[0]
        assert k.first_position == 7
        assert k.latest_position == 3


# ── ranking buckets (per-keyword, latest observation) ─────────────────────


class TestBuckets:
    def test_top_buckets_cumulative_by_latest_position(self):
        observations = (
            _obs(keyword="top1", position=1),
            _obs(keyword="top3", position=3),
            _obs(keyword="band4", position=4),
            _obs(keyword="top10", position=10),
            _obs(keyword="band11", position=11),
            _obs(keyword="top20", position=20),
            _obs(keyword="band21", position=21),
            _obs(keyword="top50", position=50),
            _obs(keyword="outside", position=51),
            _obs(keyword="deep", position=99),
        )
        m = calculate_dataset_metrics(_ds(), observations)
        assert m.keywords_with_rankings == 10
        assert m.top_3_count == 2  # 1, 3
        assert m.top_10_count == 4  # <= 10
        assert m.top_20_count == 6  # <= 20
        assert m.top_50_count == 8  # <= 50

    def test_bucket_counts_use_latest_not_best(self):
        # kw was once #1 but its LATEST observation is #30.
        obs = (
            _obs(keyword="kw", position=1, observed_at=_T0),
            _obs(keyword="kw", position=30, observed_at=_T1),
        )
        m = calculate_dataset_metrics(_ds(), obs)
        assert m.top_3_count == 0
        assert m.top_10_count == 0
        assert m.top_20_count == 0
        assert m.top_50_count == 1

    def test_outside_top_50_excluded_from_all_counts(self):
        m = calculate_dataset_metrics(_ds(), (_obs(keyword="kw", position=75),))
        assert m.top_3_count == 0
        assert m.top_10_count == 0
        assert m.top_20_count == 0
        assert m.top_50_count == 0
        assert m.keywords_with_rankings == 1


# ── visibility score ──────────────────────────────────────────────────────


class TestVisibilityScore:
    def test_weight_boundaries(self):
        cases = {
            1: 1.00,
            3: 1.00,
            4: 0.70,
            10: 0.70,
            11: 0.40,
            20: 0.40,
            21: 0.15,
            50: 0.15,
            51: 0.00,
            200: 0.00,
        }
        for position, weight in cases.items():
            obs = (_obs(keyword=f"k{position}", position=position),)
            assert calculate_visibility_score(obs) == weight

    def test_average_of_keyword_weights(self):
        # latest positions 1 and 7 → (1.00 + 0.70) / 2
        obs = (_obs(keyword="a", position=1), _obs(keyword="b", position=7))
        assert calculate_visibility_score(obs) == 0.85

    def test_visibility_uses_latest_observation(self):
        obs = (
            _obs(keyword="a", position=1, observed_at=_T0),
            _obs(keyword="a", position=40, observed_at=_T1),
        )
        assert calculate_visibility_score(obs) == 0.15

    def test_deterministic_across_runs(self):
        obs = (_obs(keyword="a", position=2), _obs(keyword="b", position=13))
        assert calculate_visibility_score(obs) == calculate_visibility_score(obs)


# ── dataset-level aggregates ──────────────────────────────────────────────


class TestDatasetMetrics:
    def test_average_median_over_all_observations(self):
        obs = (
            _obs(keyword="a", position=1, observed_at=_T0),
            _obs(keyword="b", position=2, observed_at=_T0),
            _obs(keyword="b", position=4, observed_at=_T1),
        )
        m = calculate_dataset_metrics(_ds(total_keywords=2), obs)
        assert m.total_observations == 3
        assert m.average_position == round((1 + 2 + 4) / 3, 2)
        assert m.median_position == 2.0

    def test_keywords_not_ranking_from_metadata(self):
        obs = (_obs(keyword="ranked", position=5),)
        m = calculate_dataset_metrics(_ds(total_keywords=3), obs)
        assert m.keywords_with_rankings == 1
        assert m.keywords_not_ranking == 2

    def test_keywords_not_ranking_never_negative(self):
        obs = (_obs(keyword="a", position=5), _obs(keyword="b", position=6))
        m = calculate_dataset_metrics(_ds(total_keywords=1), obs)
        assert m.keywords_not_ranking == 0


# ── competitor analysis ───────────────────────────────────────────────────


class TestCompetitorMetrics:
    def test_competitor_outranks_us(self):
        obs = (_obs(keyword="kw", position=5),)
        comps = (_comp(keyword="kw", domain="rival.io", position=2),)
        c = calculate_competitor_metrics(obs, comps)[0]
        assert c.outranking_count == 1
        assert c.outranked_count == 0

    def test_we_outrank_competitor(self):
        obs = (_obs(keyword="kw", position=1),)
        comps = (_comp(keyword="kw", domain="rival.io", position=4),)
        c = calculate_competitor_metrics(obs, comps)[0]
        assert c.outranking_count == 0
        assert c.outranked_count == 1

    def test_equal_position_counts_as_neither(self):
        obs = (_obs(keyword="kw", position=3),)
        comps = (_comp(keyword="kw", domain="rival.io", position=3),)
        c = calculate_competitor_metrics(obs, comps)[0]
        assert c.outranking_count == 0
        assert c.outranked_count == 0

    def test_missing_comparable_observation_skipped(self):
        # competitor record for a keyword we never observed → ignored, not invented
        obs = (_obs(keyword="ours", position=5),)
        comps = (_comp(keyword="unknown-kw", domain="rival.io", position=1),)
        c = calculate_competitor_metrics(obs, comps)[0]
        assert c.observed_count == 1  # record still counted as observed
        assert c.outranking_count == 0
        assert c.outranked_count == 0

    def test_comparison_uses_our_latest_observation(self):
        obs = (
            _obs(keyword="kw", position=1, observed_at=_T0),
            _obs(keyword="kw", position=8, observed_at=_T1),
        )
        comps = (_comp(keyword="kw", domain="rival.io", position=4, observed_at=_T0),)
        c = calculate_competitor_metrics(obs, comps)[0]
        # vs latest (8): rival at 4 outranks us
        assert c.outranking_count == 1
        assert c.outranked_count == 0

    def test_multiple_competitors_sorted_deterministically(self):
        obs = (_obs(keyword="kw", position=5),)
        comps = (
            _comp(keyword="kw", domain="zeta.io", position=1),
            _comp(keyword="kw", domain="alpha.io", position=2),
            _comp(keyword="kw", domain="mid.io", position=9),
        )
        result = calculate_competitor_metrics(obs, comps)
        assert [c.competitor_domain for c in result] == ["alpha.io", "mid.io", "zeta.io"]

    def test_competitor_aggregates(self):
        obs = (_obs(keyword="a", position=5), _obs(keyword="b", position=5))
        comps = (
            _comp(keyword="a", domain="rival.io", position=1),
            _comp(keyword="b", domain="rival.io", position=12),
        )
        c = calculate_competitor_metrics(obs, comps)[0]
        assert c.keyword_count == 2
        assert c.observed_count == 2
        assert c.average_position == round((1 + 12) / 2, 2)
        assert c.top_10_count == 1
        # rival position 1 < our 5 → outranks; rival position 12 > our 5 → outranked
        assert c.outranking_count == 1
        assert c.outranked_count == 1


# ── full analysis ─────────────────────────────────────────────────────────


class TestAnalyzeSearchDataset:
    def test_full_result_shape_and_ordering(self):
        obs = (
            _obs(keyword="seo tools", position=7, observed_at=_T0),
            _obs(keyword="crm software", position=3, observed_at=_T0),
            _obs(keyword="crm software", position=1, observed_at=_T1),
        )
        comps = (_comp(keyword="crm software", domain="rival.io", position=2, observed_at=_T0),)
        result = analyze_search_dataset(_ds("ds-x"), obs, comps)
        assert result.dataset_id == "ds-x"
        assert [k.keyword for k in result.keyword_metrics] == ["crm software", "seo tools"]
        assert [c.competitor_domain for c in result.competitor_metrics] == ["rival.io"]
        # latest positions: crm→1 (weight 1.00), seo tools→7 (weight 0.70)
        assert result.dataset_metrics.visibility_score == 0.85

    def test_frozen_models(self):
        from dataclasses import FrozenInstanceError

        from sie.domain.models.search_analytics import KeywordRankingMetrics

        k = KeywordRankingMetrics(
            keyword="k",
            observation_count=1,
            best_position=1,
            worst_position=1,
            average_position=1.0,
            latest_position=1,
            first_position=1,
            position_change=None,
            improved=False,
            declined=False,
        )
        with pytest.raises(FrozenInstanceError):
            k.keyword = "other"  # type: ignore[misc]

    def test_duplicate_observations_counted_individually(self):
        # identical duplicates are the import layer's concern; the engine
        # deterministically counts every observation it receives.
        obs = (
            _obs(keyword="kw", position=4, observed_at=_T0),
            _obs(keyword="kw", position=4, observed_at=_T0),
        )
        k = calculate_keyword_metrics(obs)[0]
        assert k.observation_count == 2
        assert k.average_position == 4.0
        assert k.position_change == 0  # two data points, both 4 → unchanged

    def test_invalid_positions_rejected_upstream(self):
        # engine relies on model invariants; verify they hold
        with pytest.raises(ValueError):
            _obs(position=0)
        with pytest.raises(ValueError):
            _obs(position=-3)


# ── determinism ───────────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_input_same_output(self):
        obs = (
            _obs(keyword="a", position=2, observed_at=_T0),
            _obs(keyword="b", position=9, observed_at=_T0),
            _obs(keyword="a", position=6, observed_at=_T1),
        )
        comps = (_comp(keyword="a", domain="r.io", position=3, observed_at=_T0),)
        r1 = analyze_search_dataset(_ds("ds-d"), obs, comps)
        r2 = analyze_search_dataset(_ds("ds-d"), obs, comps)
        assert r1 == r2
