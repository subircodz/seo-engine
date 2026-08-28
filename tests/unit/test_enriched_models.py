"""Tests for Cloudflare detection, website type detection, and enriched evidence models."""

from __future__ import annotations

from datetime import UTC, datetime

from sie.domain.services.site_analysis import (
    AccessStatus,
    AIODetailQuery,
    AuthorityGapDetail,
    ContentGapDetail,
    CountryActionItem,
    GEODetailQuery,
    KeywordRankingDetail,
    ReportMetadata,
    SiteAnalysisResult,
    SiteArchitectureHealth,
    SiteContentHealth,
    SiteTechnicalHealth,
    TechnicalMetricDetail,
    WebsiteTypeInfo,
)

# ════════════════════════════════════════════════════════════════════════════
# AccessStatus
# ════════════════════════════════════════════════════════════════════════════


class TestAccessStatus:
    def test_accessible_site(self):
        status = AccessStatus(accessible=True, status_code=200, analysis_status="SUCCESS")
        assert status.is_blocked is False
        assert status.accessible is True

    def test_blocked_cloudflare(self):
        status = AccessStatus(
            accessible=False,
            protection_detected="Cloudflare",
            protection_details="Cloudflare Browser Verification",
            status_code=403,
            bypass_attempted=True,
            bypass_succeeded=False,
            bypass_methods_used=["User-agent rotation", "Standard HTTP fetch"],
            analysis_status="BLOCKED",
            block_reason="Cloudflare protection detected",
            analyzed_page_is_challenge=True,
        )
        assert status.is_blocked is True
        assert status.protection_detected == "Cloudflare"
        assert status.bypass_attempted is True
        assert status.bypass_succeeded is False
        assert len(status.bypass_methods_used) == 2

    def test_blocked_waf(self):
        status = AccessStatus(
            accessible=False,
            protection_detected="WAF/Bot Protection",
            status_code=403,
            analysis_status="BLOCKED",
        )
        assert status.is_blocked is True

    def test_no_pages(self):
        status = AccessStatus(
            accessible=False,
            status_code=0,
            analysis_status="BLOCKED",
            block_reason="No pages could be retrieved.",
        )
        assert status.is_blocked is True
        assert status.status_code == 0


# ════════════════════════════════════════════════════════════════════════════
# WebsiteTypeInfo
# ════════════════════════════════════════════════════════════════════════════


class TestWebsiteTypeInfo:
    def test_wordpress_detection(self):
        info = WebsiteTypeInfo(
            technology="WordPress",
            confidence=0.85,
            evidence=["wp-content paths detected", "wp-json endpoint found"],
            cms="WordPress",
            language="en",
        )
        assert info.technology == "WordPress"
        assert info.cms == "WordPress"
        assert info.confidence == 0.85

    def test_unknown_website(self):
        info = WebsiteTypeInfo(
            technology="Unknown",
            confidence=0.0,
            evidence=["Insufficient indicators"],
        )
        assert info.technology == "Unknown"
        assert info.confidence == 0.0

    def test_nextjs_detection(self):
        info = WebsiteTypeInfo(
            technology="Next.js",
            confidence=0.9,
            evidence=["__next indicator found"],
            framework="Next.js",
            cdn="Vercel",
        )
        assert info.framework == "Next.js"
        assert info.cdn == "Vercel"


# ════════════════════════════════════════════════════════════════════════════
# KeywordRankingDetail
# ════════════════════════════════════════════════════════════════════════════


class TestKeywordRankingDetail:
    def test_ranked_keyword(self):
        detail = KeywordRankingDetail(
            keyword="online casino",
            source="discovered",
            search_location="US",
            search_engine="Google",
            language="en",
            device="desktop",
            search_date="26 August 2026",
            observed_position=37,
            checked_to="Top 100",
            ranking_url="https://power.win/casino",
            evidence="Position #37 observed in Google SERP for US",
            status="Verified",
            confidence="HIGH",
        )
        assert detail.observed_position == 37
        assert detail.status == "Verified"
        assert detail.confidence == "HIGH"

    def test_not_ranked_keyword(self):
        detail = KeywordRankingDetail(
            keyword="power win",
            source="discovered",
            search_location="US",
            search_engine="Google",
            language="en",
            device="desktop",
            search_date="26 August 2026",
            observed_position=None,
            checked_to="Top 100",
            evidence="No ranking found in top 100 results",
            status="Verified",
            confidence="MEDIUM",
        )
        assert detail.observed_position is None
        assert detail.status == "Verified"
        assert detail.confidence == "MEDIUM"

    def test_unverifiable_keyword(self):
        detail = KeywordRankingDetail(
            keyword="test",
            source="discovered",
            search_location="US",
            search_engine="Google",
            language="en",
            device="desktop",
            search_date="26 August 2026",
            observed_position=None,
            checked_to="Top 100",
            evidence="Search query failed — ranking could not be verified",
            status="Could Not Verify",
            confidence="LOW",
        )
        assert detail.status == "Could Not Verify"
        assert detail.confidence == "LOW"


# ════════════════════════════════════════════════════════════════════════════
# AIODetailQuery
# ════════════════════════════════════════════════════════════════════════════


class TestAIODetailQuery:
    def test_ai_overview_detected(self):
        q = AIODetailQuery(
            keyword="online casino",
            ai_overview_detected=True,
            target_cited=False,
            cited_sources=["stake.com", "bet365.com"],
            search_location="US",
            search_date="26 August 2026",
            evidence="AI Overview detected. power.win not cited.",
        )
        assert q.ai_overview_detected is True
        assert q.target_cited is False
        assert len(q.cited_sources) == 2

    def test_no_ai_overview(self):
        q = AIODetailQuery(
            keyword="power win",
            ai_overview_detected=False,
            target_cited=False,
            evidence="AI Overview not detected",
        )
        assert q.ai_overview_detected is False


# ════════════════════════════════════════════════════════════════════════════
# GEODetailQuery
# ════════════════════════════════════════════════════════════════════════════


class TestGEODetailQuery:
    def test_mentioned(self):
        q = GEODetailQuery(
            query="online casino",
            engine="General",
            target_mentioned=True,
            competitors_mentioned=["stake.com"],
            evidence="Domain mentioned in generative engine response",
        )
        assert q.target_mentioned is True

    def test_not_mentioned(self):
        q = GEODetailQuery(
            query="power win",
            engine="General",
            target_mentioned=False,
            competitors_mentioned=[],
            evidence="Domain not mentioned",
        )
        assert q.target_mentioned is False
        assert len(q.competitors_mentioned) == 0


# ════════════════════════════════════════════════════════════════════════════
# TechnicalMetricDetail
# ════════════════════════════════════════════════════════════════════════════


class TestTechnicalMetricDetail:
    def test_passing_metric(self):
        m = TechnicalMetricDetail(
            metric_name="SSL/HTTPS",
            weight=10.0,
            expected_score=100.0,
            actual_score=100.0,
            status="PASS",
            evidence="All pages served over HTTPS",
            what_was_checked="HTTPS accessibility",
            why_it_matters="HTTPS is a ranking signal",
            remediation="Ensure all pages use HTTPS",
            reference_url="https://developers.google.com/search/docs/security/https",
        )
        assert m.status == "PASS"
        assert m.actual_score == 100.0
        assert m.reference_url is not None

    def test_failing_metric(self):
        m = TechnicalMetricDetail(
            metric_name="Performance",
            weight=20.0,
            expected_score=100.0,
            actual_score=45.0,
            status="NEEDS IMPROVEMENT",
            evidence="Average page load time: 3000ms",
            what_was_checked="HTTP response time",
            what_failed="Slow response times",
            why_it_matters="Slow pages increase bounce rate",
            remediation="Optimize server and assets",
        )
        assert m.status == "NEEDS IMPROVEMENT"
        assert m.actual_score < m.expected_score
        assert m.what_failed != ""


# ════════════════════════════════════════════════════════════════════════════
# ReportMetadata
# ════════════════════════════════════════════════════════════════════════════


class TestReportMetadata:
    def test_human_readable_dates(self):
        meta = ReportMetadata(
            target_url="https://power.win",
            analysis_date="26 August 2026",
            analysis_started="26 August 2026, 11:00 AM UTC",
            analysis_completed="26 August 2026, 11:05 AM UTC",
            report_generated="26 August 2026, 11:05 AM UTC",
            timezone="UTC",
            country="US",
            language="en",
            device="desktop",
            search_engine="Google",
            analysis_duration_seconds=300.0,
            pages_crawled=1,
        )
        assert "August 2026" in meta.analysis_date
        assert "AM" in meta.analysis_started
        assert meta.analysis_duration_seconds == 300.0
        assert meta.timezone == "UTC"

    def test_defaults(self):
        meta = ReportMetadata()
        assert meta.target_url == ""
        assert meta.analysis_date == ""
        assert meta.timezone == "UTC"


# ════════════════════════════════════════════════════════════════════════════
# Content/Authority Gap Details
# ════════════════════════════════════════════════════════════════════════════


class TestContentGapDetail:
    def test_gap_detail(self):
        gap = ContentGapDetail(
            keyword="online casino, power win",
            search_intent="commercial",
            site_pages_addressing=0,
            competitor_pages_addressing=5,
            competitor_domains=["stake.com", "bet365.com"],
            missing_topics=["payment methods", "game variety", "bonuses"],
            recommendation="Create comprehensive casino review page",
        )
        assert gap.site_pages_addressing == 0
        assert gap.competitor_pages_addressing == 5
        assert len(gap.missing_topics) == 3


class TestAuthorityGapDetail:
    def test_no_backlink_data(self):
        gap = AuthorityGapDetail(
            backlink_data_available=False,
            comparison_methodology="Not assessed",
            limitation="No reliable backlink dataset available",
            confidence="LOW",
        )
        assert gap.backlink_data_available is False
        assert gap.confidence == "LOW"
        assert "no" in gap.limitation.lower() or "not" in gap.limitation.lower()


# ════════════════════════════════════════════════════════════════════════════
# Country Action Item
# ════════════════════════════════════════════════════════════════════════════


class TestCountryActionItem:
    def test_action_item(self):
        item = CountryActionItem(
            title="Create US-specific landing pages",
            why_applicable="No US rankings detected",
            priority="P0",
            implementation="Create content targeting US search intent with local signals",
            reference_url="https://developers.google.com/search/docs/international",
            expected_outcome="Improved US search visibility within 3-6 months",
        )
        assert item.priority == "P0"
        assert item.reference_url is not None
        assert item.expected_outcome != ""


# ════════════════════════════════════════════════════════════════════════════
# SiteAnalysisResult Integration
# ════════════════════════════════════════════════════════════════════════════


class TestSiteAnalysisResultIntegration:
    def test_result_with_all_enriched_fields(self):
        result = SiteAnalysisResult(
            domain="power.win",
            analyzed_at=datetime.now(UTC),
            crawl_run_id="test123",
            technical_score=85.0,
            content_score=65.0,
            ranking_score=0.0,
            architecture_score=95.0,
            aio_score=10.0,
            geo_score=50.0,
            overall_score=50.8,
            access_status=AccessStatus(accessible=True, status_code=200, analysis_status="SUCCESS"),
            website_type=WebsiteTypeInfo(technology="WordPress", confidence=0.8),
            report_metadata=ReportMetadata(analysis_date="26 August 2026"),
            analysis_started_at=datetime.now(UTC),
            analysis_completed_at=datetime.now(UTC),
        )
        assert result.access_status is not None
        assert result.access_status.accessible is True
        assert result.website_type is not None
        assert result.website_type.technology == "WordPress"
        assert result.report_metadata is not None

    def test_result_blocked(self):
        result = SiteAnalysisResult(
            domain="power.win",
            analyzed_at=datetime.now(UTC),
            crawl_run_id="test456",
            technical_score=0.0,
            content_score=0.0,
            ranking_score=0.0,
            architecture_score=0.0,
            overall_score=0.0,
            access_status=AccessStatus(
                accessible=False,
                analysis_status="BLOCKED",
                protection_detected="Cloudflare",
                analyzed_page_is_challenge=True,
            ),
            website_type=WebsiteTypeInfo(technology="Unknown", confidence=0.0),
        )
        assert result.access_status.is_blocked is True
        assert result.overall_score == 0.0


# ════════════════════════════════════════════════════════════════════════════
# PDF Template Rendering (smoke test)
# ════════════════════════════════════════════════════════════════════════════


class TestPDFTemplateRendering:
    def test_accessible_report_renders(self):
        from sie.domain.renderers.pdf_renderer import PDFRenderer

        result = SiteAnalysisResult(
            domain="test.com",
            analyzed_at=datetime.now(UTC),
            crawl_run_id="test",
            technical_score=80.0,
            content_score=70.0,
            ranking_score=50.0,
            architecture_score=90.0,
            aio_score=60.0,
            geo_score=55.0,
            overall_score=67.5,
            technical=SiteTechnicalHealth(
                pages_crawled=5,
                critical_issues=0,
                warning_issues=2,
                info_issues=0,
                indexable_pages=5,
                non_indexable_pages=0,
                avg_load_time_ms=500.0,
                core_web_vitals_pass=True,
                has_ssl=True,
                robots_txt_valid=True,
                sitemap_exists=True,
                metric_details=[
                    TechnicalMetricDetail(
                        "SSL/HTTPS",
                        10,
                        100,
                        100,
                        "PASS",
                        evidence="OK",
                    ),
                    TechnicalMetricDetail(
                        "Crawlability",
                        15,
                        100,
                        95,
                        "PASS",
                        evidence="95% indexable",
                    ),
                    TechnicalMetricDetail(
                        "Performance",
                        20,
                        100,
                        80,
                        "PASS",
                        evidence="500ms avg",
                    ),
                    TechnicalMetricDetail(
                        "Robots.txt",
                        10,
                        100,
                        75,
                        "NEEDS IMPROVEMENT",
                        evidence="Missing directives",
                        remediation="Update robots.txt",
                    ),
                    TechnicalMetricDetail(
                        "XML Sitemap",
                        10,
                        100,
                        80,
                        "NEEDS IMPROVEMENT",
                        evidence="Incomplete",
                        remediation="Add all pages",
                    ),
                    TechnicalMetricDetail(
                        "Issue Density",
                        15,
                        100,
                        95,
                        "PASS",
                        evidence="Low density",
                    ),
                    TechnicalMetricDetail(
                        "Indexability",
                        20,
                        100,
                        100,
                        "PASS",
                        evidence="All indexable",
                    ),
                ],
            ),
            content=SiteContentHealth(
                pages_analyzed=5,
                avg_quality_score=0.7,
                thin_content_pages=0,
                duplicate_groups=0,
                missing_h1_pages=0,
                missing_meta_desc_pages=0,
                low_word_count_pages=0,
            ),
            architecture=SiteArchitectureHealth(
                total_pages=5,
                total_internal_links=20,
                avg_depth=2.0,
                orphan_pages=0,
                max_depth=4,
            ),
            access_status=AccessStatus(
                accessible=True,
                status_code=200,
                analysis_status="SUCCESS",
            ),
            website_type=WebsiteTypeInfo(
                technology="WordPress",
                confidence=0.8,
                evidence=["wp-content detected"],
            ),
            report_metadata=ReportMetadata(
                target_url="https://test.com",
                analysis_date="26 August 2026",
                analysis_started="26 Aug 2026, 11 AM UTC",
                analysis_completed="26 Aug 2026, 11 AM UTC",
                country="US",
                analysis_duration_seconds=300.0,
                pages_crawled=5,
            ),
        )
        renderer = PDFRenderer()
        pdf = renderer.render(result)
        assert len(pdf) > 5000
        assert pdf[:4] == b"%PDF"

    def test_blocked_report_renders(self):
        from sie.domain.renderers.pdf_renderer import PDFRenderer

        result = SiteAnalysisResult(
            domain="blocked.com",
            analyzed_at=datetime.now(UTC),
            crawl_run_id="test",
            technical_score=0.0,
            content_score=0.0,
            ranking_score=0.0,
            architecture_score=0.0,
            overall_score=0.0,
            access_status=AccessStatus(
                accessible=False,
                status_code=403,
                analysis_status="BLOCKED",
                protection_detected="Cloudflare",
                protection_details="JavaScript challenge",
                bypass_attempted=True,
                bypass_succeeded=False,
                bypass_methods_used=["User-agent rotation"],
                block_reason="Cloudflare protection",
                analyzed_page_is_challenge=True,
            ),
            website_type=WebsiteTypeInfo(
                technology="Unknown",
                confidence=0.0,
                evidence=["Challenge page"],
            ),
            report_metadata=ReportMetadata(
                target_url="https://blocked.com",
                analysis_date="26 August 2026",
                country="US",
            ),
        )
        renderer = PDFRenderer()
        pdf = renderer.render(result)
        assert len(pdf) > 3000
        assert pdf[:4] == b"%PDF"
