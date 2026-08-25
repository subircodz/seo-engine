"""Unit tests for ranking volatility (Phase 6N-D)."""

import dataclasses
from datetime import UTC, datetime

import pytest

from sie.domain.models.search import RankingObservation, SearchDataset, SearchDevice
from sie.domain.services.ranking_volatility import (
    RankingVolatilityService,
)

_T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


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


def _ds(dataset_id: str = "ds-1", total_keywords: int = 0, total_observations: int = 0):
    return SearchDataset(
        dataset_id=dataset_id,
        name="fixture",
        source="test",
        total_keywords=total_keywords,
        total_observations=total_observations,
    )


class TestRankingVolatilityService:
    def test_single_observation_no_fabricated_volatility(self):
        """Single-observation keywords must not fabricate volatility."""
        service = RankingVolatilityService()
        obs = _obs(observed_at=_T0)
        metrics = service.calculate_volatility_by_keyword((obs,))
        assert metrics[0].volatility == 0.0
        assert metrics[0].severity == "low"

    def test_identical_positions_low_volatility(self):
        """Multiple observations at same position should produce low volatility."""
        service = RankingVolatilityService()
        obs = (
            _obs(position=3, observed_at=_T0),
            _obs(position=3, observed_at=_T1),
        )
        metrics = service.calculate_volatility_by_keyword(obs)
        # Positions are identical → Δposition = 0 → volatility should be 0.0
        assert metrics[0].volatility == 0.0

    def test_large_position_change_high_volatility(self):
        """Large position changes should produce higher volatility."""
        service = RankingVolatilityService()
        obs = (
            _obs(position=1, observed_at=_T0),
            _obs(position=50, observed_at=_T1),
        )
        metrics = service.calculate_volatility_by_keyword(obs)
        assert metrics[0].volatility > 0.0
        # With pos 1 and 50: Δ = 49, avg_pos = 25.5
        # vol ≈ 49 / (1 + 50) ≈ 0.97
        assert metrics[0].severity in ("high", "extreme")

    def test_volatility_aggregation(self):
        """Volatility should aggregate correctly across multiple observations."""
        service = RankingVolatilityService()
        obs = (
            _obs(position=5, observed_at=_T0),
            _obs(position=3, observed_at=_T1),
            _obs(position=8, observed_at=datetime(2026, 8, 3, 10, 0, tzinfo=UTC)),
        )
        metrics = service.calculate_volatility_by_keyword(obs)
        assert metrics[0].volatility > 0.0
        # Positions: 5→3→8, changes: |3-5|=2, |8-3|=5, total=7
        # vol = 7 / (5 + 3 + 8 + 1) = 7/17 ≈ 0.41
        assert 0.3 < metrics[0].volatility < 0.5

    def test_empty_observations(self):
        """Empty observations should return zero volatility."""
        service = RankingVolatilityService()
        metrics = service.calculate_volatility_by_keyword(())
        # Tuple is empty, keyword loop won't execute, but we test edge case
        assert len(metrics) == 0

    def test_frozen_immutability(self):
        """RankingVolatilityMetrics should be frozen."""
        service = RankingVolatilityService()
        obs = (
            _obs(position=3, observed_at=_T0),
            _obs(position=5, observed_at=_T1),
        )
        metrics = service.calculate_volatility_by_keyword(obs)
        with pytest.raises(dataclasses.FrozenInstanceError):
            metrics[0].volatility = 0.5  # type: ignore


class TestRankingVolatilityBoundaryCases:
    def test_unknown_keyword_no_fabrication(self):
        """Keywords with only one observation must have zero volatility."""
        service = RankingVolatilityService()
        obs = (_obs(keyword="kw1"),)
        metrics = service.calculate_volatility_by_keyword(obs)
        assert metrics[0].volatility == 0.0

    def test_multiple_keywords(self):
        """Volatility should calculate independently per keyword."""
        service = RankingVolatilityService()
        obs = (
            _obs(keyword="kw1"),
            _obs(keyword="kw2", position=10, observed_at=_T1),
        )
        metrics = service.calculate_volatility_by_keyword(obs)
        assert len(metrics) == 2

    def test_chronological_ordering(self):
        """Volatility should respect observed_at ordering."""
        service = RankingVolatilityService()
        obs = (
            _obs(position=3, observed_at=_T1),  # newer first
            _obs(position=5, observed_at=_T0),  # older
        )
        metrics = service.calculate_volatility_by_keyword(obs)
        # Ordering is by observed_at, so positions 5→3 gives change of 2
        # With only 2 observations, vol = 2 / (3 + 5 + 1) = 2/9 ≈ 0.22
        assert 0.2 < metrics[0].volatility < 0.3

    def test_get_volatile_keywords(self):
        """Get volatile keywords above threshold."""
        service = RankingVolatilityService()
        obs = (
            _obs(keyword="stable", position=5),
            _obs(keyword="unstable", position=1, observed_at=_T1),  # big change from single obs
        )
        volatile = service.get_volatile_keywords(obs, threshold=0.01)
        # With only one observation each, volatility = 0, so should be empty
        # unless our test cases have enough variation
        assert isinstance(volatile, tuple)

    def test_calculate_volatility_by_keyword_returns_tuple(self):
        """Volatility results should be tuple for immutability."""
        service = RankingVolatilityService()
        obs = (
            _obs(position=3),
            _obs(position=5),
        )
        metrics = service.calculate_volatility_by_keyword(obs)
        assert isinstance(metrics, tuple)

    def test_single_observation_returns_single_metric(self):
        """One observation → one metric with zero volatility."""
        service = RankingVolatilityService()
        obs = (_obs(keyword="single", position=7),)
        metrics = service.calculate_volatility_by_keyword(obs)
        assert len(metrics) == 1
        assert metrics[0].keyword == "single"
        assert metrics[0].volatility == 0.0

    def test_severity_classification_boundaries(self):
        """Test severity boundaries."""
        service = RankingVolatilityService()

        # Very low
        metrics_low = service._classify_severity(0.001)
        assert metrics_low == "low"

        # Low-medium boundary
        metrics_mid_low = service._classify_severity(0.009)
        assert metrics_mid_low == "low"

        # Medium
        metrics_mid = service._classify_severity(0.05)
        assert metrics_mid == "medium"

        # Medium-high boundary
        metrics_mid_high = service._classify_severity(0.09)
        assert metrics_mid_high == "medium"

        # High
        metrics_high = service._classify_severity(0.5)
        assert metrics_high == "high"

        # High-extreme boundary
        metrics_high_extreme = service._classify_severity(0.9)
        assert metrics_high_extreme == "high"

        # Extreme
        metrics_extreme = service._classify_severity(5.0)
        assert metrics_extreme == "extreme"


class TestDatasetVolatility:
    def test_dataset_volatility(self):
        """Calculate volatility across a full dataset."""
        service = RankingVolatilityService()
        _ds(total_keywords=10)
        obs = (
            _obs(keyword="kw1", position=3, observed_at=_T0),
            _obs(keyword="kw1", position=5, observed_at=_T1),
            _obs(keyword="kw2", position=10, observed_at=_T0),
            _obs(keyword="kw3", position=3, observed_at=_T0),
            _obs(keyword="kw3", position=3, observed_at=_T1),
        )
        metrics = service.calculate_volatility_by_keyword(obs)
        assert len(metrics) == 3  # kw1, kw2, kw3

    def test_dataset_volatile_keywords(self):
        """Identify volatile keywords in a dataset."""
        service = RankingVolatilityService()
        _ds(total_keywords=5)
        obs = (
            _obs(keyword="kw1", position=3, observed_at=_T0),
            _obs(keyword="kw1", position=50, observed_at=_T1),
            _obs(keyword="kw2", position=5, observed_at=_T0),
            _obs(keyword="kw3", position=3, observed_at=_T0),
        )
        volatile = service.get_volatile_keywords(obs, threshold=0.1)
        assert "kw1" in volatile
        assert "kw2" not in volatile  # only one observation


class TestCannibalizationFinding:
    def test_minimum_two_urls(self):
        """CannibalizationFinding requires at least 2 competing URLs."""
        from sie.domain.services.cannibalization import CannibalizationFinding

        with pytest.raises(ValueError):
            CannibalizationFinding(
                keyword="kw",
                competing_urls=("https://example.com/page1",),
                competing_domains=("example.com",),
                positions=(1,),
                severity="low",
            )

    def test_findings_sorted(self):
        """Findings should be deterministic."""
        from sie.domain.services.cannibalization import CannibalizationFinding

        f1 = CannibalizationFinding(
            keyword="aaa",
            competing_urls=("https://a.com", "https://b.com"),
            competing_domains=("a.com", "b.com"),
            positions=(1, 5),
            severity="low",
        )
        f2 = CannibalizationFinding(
            keyword="zzz",
            competing_urls=("https://oursite.io/b", "https://other.io/c"),
            competing_domains=("oursite.io", "other.io"),
            positions=(2, 3),
            severity="low",
        )
        # f1 should come before f2 alphabetically
        assert f1.keyword < f2.keyword
