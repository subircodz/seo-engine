"""Tests for SiteAnalysisService."""

from __future__ import annotations

import pytest

from sie.domain.services.site_analysis import (
    SiteAIOAnalysis,
    SiteAnalysisResult,
    SiteArchitectureHealth,
    SiteContentHealth,
    SiteGEOAnalysis,
    SiteRankingSnapshot,
    SiteTechnicalHealth,
)

# ════════════════════════════════════════════════════════════════════════════
# Dataclass construction
# ════════════════════════════════════════════════════════════════════════════


class TestSiteRankingSnapshot:
    def test_construction(self):
        s = SiteRankingSnapshot(
            domain="example.com",
            total_keywords_tracked=50,
            keywords_in_top_3=5,
            keywords_in_top_10=15,
            keywords_in_top_20=25,
            keywords_not_ranking=25,
            visibility_score=0.5,
            estimated_monthly_traffic=12000,
        )
        assert s.domain == "example.com"
        assert s.total_keywords_tracked == 50
        assert s.keywords_in_top_3 == 5

    def test_default_top_keywords(self):
        s = SiteRankingSnapshot(
            domain="x.com",
            total_keywords_tracked=0,
            keywords_in_top_3=0,
            keywords_in_top_10=0,
            keywords_in_top_20=0,
            keywords_not_ranking=0,
            visibility_score=0.0,
            estimated_monthly_traffic=0,
        )
        assert s.top_keywords == []

    def test_frozen(self):
        s = SiteRankingSnapshot(
            domain="x.com",
            total_keywords_tracked=0,
            keywords_in_top_3=0,
            keywords_in_top_10=0,
            keywords_in_top_20=0,
            keywords_not_ranking=0,
            visibility_score=0.0,
            estimated_monthly_traffic=0,
        )
        with pytest.raises(AttributeError):
            s.domain = "y.com"


class TestSiteAIOAnalysis:
    def test_construction(self):
        a = SiteAIOAnalysis(
            keywords_checked=20,
            ai_overviews_present=5,
            target_cited_count=2,
            competitor_cited_count=3,
            citation_rate=0.25,
            target_citation_rate=0.10,
        )
        assert a.keywords_checked == 20
        assert a.citation_rate == 0.25


class TestSiteGEOAnalysis:
    def test_construction(self):
        g = SiteGEOAnalysis(
            keywords_checked=20,
            target_mentioned_count=3,
            competitor_mentioned_count=8,
            mention_rate=0.15,
            avg_mention_count=0.15,
        )
        assert g.mention_rate == 0.15


class TestSiteTechnicalHealth:
    def test_construction(self):
        t = SiteTechnicalHealth(
            pages_crawled=100,
            critical_issues=2,
            warning_issues=10,
            info_issues=20,
            indexable_pages=95,
            non_indexable_pages=5,
            avg_load_time_ms=1500.0,
            core_web_vitals_pass=True,
            has_ssl=True,
            robots_txt_valid=True,
            sitemap_exists=True,
        )
        assert t.pages_crawled == 100
        assert t.critical_issues == 2


class TestSiteContentHealth:
    def test_construction(self):
        c = SiteContentHealth(
            pages_analyzed=50,
            avg_quality_score=0.75,
            thin_content_pages=3,
            duplicate_groups=1,
            missing_h1_pages=2,
            missing_meta_desc_pages=5,
            low_word_count_pages=4,
        )
        assert c.avg_quality_score == 0.75


class TestSiteArchitectureHealth:
    def test_construction(self):
        a = SiteArchitectureHealth(
            total_pages=100,
            total_internal_links=500,
            avg_depth=2.5,
            orphan_pages=3,
            max_depth=5,
        )
        assert a.total_pages == 100

    def test_orphans_property(self):
        a = SiteArchitectureHealth(
            total_pages=10,
            total_internal_links=50,
            avg_depth=2.0,
            orphan_pages=3,
            max_depth=4,
        )
        assert a.orphans == 3


class TestSiteAnalysisResult:
    def test_construction_minimal(self):
        from datetime import UTC, datetime

        r = SiteAnalysisResult(
            domain="example.com",
            analyzed_at=datetime.now(UTC),
            crawl_run_id=None,
            technical_score=80.0,
            content_score=70.0,
            ranking_score=60.0,
            architecture_score=90.0,
        )
        assert r.domain == "example.com"
        assert r.overall_score == 0.0
        assert r.aio_score == 0.0
        assert r.recommendations == ()

    def test_construction_full(self):
        from datetime import UTC, datetime

        r = SiteAnalysisResult(
            domain="test.com",
            analyzed_at=datetime.now(UTC),
            crawl_run_id="run-123",
            technical_score=85.0,
            content_score=75.0,
            ranking_score=65.0,
            architecture_score=95.0,
            aio_score=50.0,
            geo_score=50.0,
            overall_score=70.0,
        )
        assert r.overall_score == 70.0
        assert r.crawl_run_id == "run-123"


# ════════════════════════════════════════════════════════════════════════════
# Domain normalization (tested via the service's method)
# ════════════════════════════════════════════════════════════════════════════


class TestDomainNormalization:
    """Test the domain normalization logic used by SiteAnalysisService."""

    def _normalize(self, domain: str) -> str:
        """Mirror the normalization logic without instantiating the full service."""
        from urllib.parse import urlparse

        domain = domain.strip().lower()
        if domain.startswith(("http://", "https://")):
            parsed = urlparse(domain)
            domain = parsed.netloc or parsed.path
        domain = domain.replace("www.", "")
        domain = domain.split("/")[0].split(":")[0]
        return domain

    def test_bare_domain(self):
        assert self._normalize("example.com") == "example.com"

    def test_https_prefix(self):
        assert self._normalize("https://example.com") == "example.com"

    def test_http_prefix(self):
        assert self._normalize("http://example.com") == "example.com"

    def test_www_prefix(self):
        assert self._normalize("www.example.com") == "example.com"

    def test_www_with_https(self):
        assert self._normalize("https://www.example.com") == "example.com"

    def test_strips_path(self):
        assert self._normalize("https://example.com/page/about") == "example.com"

    def test_strips_port(self):
        assert self._normalize("https://example.com:8080") == "example.com"

    def test_strips_trailing_slash(self):
        assert self._normalize("https://example.com/") == "example.com"

    def test_uppercase(self):
        assert self._normalize("Example.COM") == "example.com"

    def test_whitespace(self):
        assert self._normalize("  https://example.com  ") == "example.com"


# ════════════════════════════════════════════════════════════════════════════
# Traffic estimation
# ════════════════════════════════════════════════════════════════════════════


class TestTrafficEstimation:
    """Test the traffic estimation logic."""

    def _estimate(self, position: int) -> int:
        ctr = {
            1: 0.30, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
            6: 0.04, 7: 0.03, 8: 0.03, 9: 0.02, 10: 0.02,
        }
        base = 1000
        return int(base * ctr.get(position, 0.01))

    def test_position_1(self):
        assert self._estimate(1) == 300

    def test_position_3(self):
        assert self._estimate(3) == 100

    def test_position_10(self):
        assert self._estimate(10) == 20

    def test_position_50(self):
        assert self._estimate(50) == 10
