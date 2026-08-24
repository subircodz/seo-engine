"""Unit tests for cannibalization detection (Phase 6N-D)."""

from datetime import UTC, datetime

import dataclasses

import pytest

from sie.domain.models.search import RankingObservation, SearchDataset, SearchDevice
from sie.domain.services.cannibalization import CannibalizationDetector, CannibalizationFinding

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


class TestCannibalizationDetector:
    def test_no_cannibalization_single_url(self):
        """Single URL per keyword = no cannibalization."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1"),
            _obs(keyword="kw1", observed_at=_T1),
        )
        findings = detector.detect_cannibalization(obs)
        assert findings == ()

    def test_two_competing_urls(self):
        """Two distinct URLs competing for same keyword should be detected."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=7),
        )
        findings = detector.detect_cannibalization(obs)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.keyword == "kw1"
        assert len(finding.competing_urls) == 2
        assert "https://oursite.io/page1" in finding.competing_urls
        assert "https://oursite.io/page2" in finding.competing_urls
        assert finding.positions == (3, 7)

    def test_multiple_competing_urls(self):
        """Three or more distinct URLs for same keyword."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=7),
            _obs(keyword="kw1", url="https://oursite.io/page3", position=12),
        )
        findings = detector.detect_cannibalization(obs)
        assert len(findings) == 1
        finding = findings[0]
        assert len(finding.competing_urls) == 3
        assert finding.positions == (3, 7, 12)

    def test_repeated_observations_same_url_not_cannibalization(self):
        """Repeated observations of the same URL should not be cannibalization."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3, observed_at=_T0),
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3, observed_at=_T1),
            _obs(
                keyword="kw1",
                url="https://oursite.io/page1",
                position=4,
                observed_at=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
            ),
        )
        findings = detector.detect_cannibalization(obs)
        assert findings == ()

    def test_severity_low_close_positions(self):
        """Close positions should have low severity."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=4),
        )
        findings = detector.detect_cannibalization(obs)
        assert findings[0].severity == "low"

    def test_severity_medium(self):
        """Medium spread positions should have medium severity."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=7),
        )
        findings = detector.detect_cannibalization(obs)
        assert findings[0].severity == "medium"

    def test_severity_high(self):
        """High spread positions should have high severity."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=12),
        )
        findings = detector.detect_cannibalization(obs)
        assert findings[0].severity == "high"

    def test_severity_extreme(self):
        """Very high spread positions should have extreme severity."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=1),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=50),
        )
        findings = detector.detect_cannibalization(obs)
        assert findings[0].severity == "extreme"

    def test_deterministic_ordering(self):
        """Findings should be sorted by keyword for deterministic output."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="zzz", url="https://oursite.io/a", position=1),
            _obs(keyword="zzz", url="https://oursite.io/b", position=2),
            _obs(keyword="aaa", url="https://oursite.io/c", position=1),
            _obs(keyword="aaa", url="https://oursite.io/d", position=2),
        )
        findings = detector.detect_cannibalization(obs)
        assert len(findings) == 2
        assert findings[0].keyword == "aaa"
        assert findings[1].keyword == "zzz"

    def test_single_observation_no_cannibalization(self):
        """Single observation per keyword = no cannibalization."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
        )
        findings = detector.detect_cannibalization(obs)
        assert findings == ()

    def test_empty_dataset(self):
        """Empty dataset should return empty findings."""
        detector = CannibalizationDetector()
        findings = detector.detect_cannibalization(())
        assert findings == ()

    def test_different_keywords_independent(self):
        """Cannibalization should be independent per keyword."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=7),
            _obs(keyword="kw2", url="https://oursite.io/page3", position=1),
            _obs(keyword="kw2", url="https://oursite.io/page4", position=2),
        )
        findings = detector.detect_cannibalization(obs)
        assert len(findings) == 2

    def test_cannibalization_with_different_domains(self):
        """Cannibalization should track domains of competing URLs."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
            _obs(keyword="kw1", url="https://blog.oursite.io/page2", position=7),
        )
        findings = detector.detect_cannibalization(obs)
        assert "oursite.io" in findings[0].competing_domains
        assert "blog.oursite.io" in findings[0].competing_domains

    def test_latest_observation_used_for_position(self):
        """Should use latest observation per URL for position."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3, observed_at=_T0),
            _obs(keyword="kw1", url="https://oursite.io/page1", position=1, observed_at=_T1),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=5, observed_at=_T0),
        )
        findings = detector.detect_cannibalization(obs)
        # page1 latest is position 1 (at _T1), page2 is position 5
        assert findings[0].positions == (1, 5)


class TestCannibalizationFindingModel:
    def test_frozen_immutability(self):
        """CannibalizationFinding should be frozen."""
        finding = CannibalizationFinding(
            keyword="kw",
            competing_urls=("https://a.com", "https://b.com"),
            competing_domains=("a.com", "b.com"),
            positions=(1, 2),
            severity="low",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            finding.keyword = "other"  # type: ignore

    def test_get_cannibalized_keywords(self):
        """Get list of cannibalized keywords."""
        detector = CannibalizationDetector()
        obs = (
            _obs(keyword="kw1", url="https://oursite.io/page1", position=3),
            _obs(keyword="kw1", url="https://oursite.io/page2", position=7),
            _obs(keyword="kw2", url="https://oursite.io/page3", position=1),
        )
        keywords = detector.get_cannibalized_keywords(obs)
        assert keywords == ("kw1",)
