"""Unit tests for Performance Intelligence engine (Phase 8)."""

from __future__ import annotations

import pytest

from sie.domain.engines.search_performance import (
    analyze_dataset_performance,
    analyze_page_performance,
)
from sie.domain.models.search_performance import (
    PagePerformanceMetrics,
    PerformanceDatasetMetrics,
    PerformanceFinding,
    PerformanceResult,
    PerformanceSeverity,
    ResourceMetric,
)


# ════════════════════════════════════════════════════════════════════════════
# ResourceMetric
# ════════════════════════════════════════════════════════════════════════════


class TestResourceMetric:
    def test_basic(self):
        m = ResourceMetric(resource_type="css", count=3, total_size_bytes=9000)
        assert m.resource_type == "css"
        assert m.count == 3
        assert m.total_size_bytes == 9000
        assert m.avg_size_bytes == 3000.0

    def test_avg_size_zero_count(self):
        m = ResourceMetric(resource_type="js", count=0, total_size_bytes=0)
        assert m.avg_size_bytes == 0.0

    def test_negative_count_raises(self):
        with pytest.raises(ValueError, match="count must be >= 0"):
            ResourceMetric(resource_type="css", count=-1)


# ════════════════════════════════════════════════════════════════════════════
# PagePerformanceMetrics
# ════════════════════════════════════════════════════════════════════════════


class TestPagePerformanceMetrics:
    def test_valid(self):
        m = PagePerformanceMetrics(url="http://example.com", html_size_bytes=50000)
        assert m.html_size_bytes == 50000
        assert m.content_efficiency == 0.0

    def test_negative_size_raises(self):
        with pytest.raises(ValueError, match="html_size_bytes must be >= 0"):
            PagePerformanceMetrics(url="http://example.com", html_size_bytes=-1)

    def test_efficiency_out_of_range_raises(self):
        with pytest.raises(ValueError, match="content_efficiency must be"):
            PagePerformanceMetrics(
                url="http://example.com", content_efficiency=1.5
            )


# ════════════════════════════════════════════════════════════════════════════
# analyze_page_performance
# ════════════════════════════════════════════════════════════════════════════


class TestAnalyzePagePerformance:
    def test_empty_page(self):
        result = analyze_page_performance(url="http://example.com")
        assert result.url == "http://example.com"
        assert result.metrics.html_size_bytes == 0
        assert result.performance_score == 1.0
        assert len(result.findings) == 0

    def test_large_html(self):
        result = analyze_page_performance(
            url="http://example.com", html_size=200000
        )
        assert result.metrics.html_size_bytes == 200000
        # Should have at least one HTML size finding
        size_findings = [f for f in result.findings if f.metric_name == "html_size"]
        assert len(size_findings) == 1
        assert size_findings[0].severity == PerformanceSeverity.HIGH

    def test_very_large_html(self):
        result = analyze_page_performance(
            url="http://example.com", html_size=600000
        )
        size_findings = [f for f in result.findings if f.metric_name == "html_size"]
        assert len(size_findings) == 1
        assert size_findings[0].severity == PerformanceSeverity.CRITICAL

    def test_low_content_efficiency(self):
        result = analyze_page_performance(
            url="http://example.com",
            html_size=100000,
            visible_text="short text",
        )
        assert result.metrics.content_efficiency > 0
        eff_findings = [
            f for f in result.findings if f.metric_name == "content_efficiency"
        ]
        assert len(eff_findings) == 1
        assert eff_findings[0].severity in (
            PerformanceSeverity.HIGH,
            PerformanceSeverity.CRITICAL,
        )

    def test_images_without_alt(self):
        result = analyze_page_performance(
            url="http://example.com", image_count=10, images_without_alt=5
        )
        alt_findings = [
            f for f in result.findings if f.metric_name == "images_without_alt"
        ]
        assert len(alt_findings) == 1
        assert alt_findings[0].severity == PerformanceSeverity.HIGH

    def test_many_resources(self):
        result = analyze_page_performance(
            url="http://example.com", css_count=50, js_count=60
        )
        resource_findings = [
            f for f in result.findings if f.metric_name == "resource_count"
        ]
        assert len(resource_findings) == 1

    def test_score_starts_at_one(self):
        result = analyze_page_performance(url="http://example.com")
        assert result.performance_score == 1.0

    def test_score_deducts_for_findings(self):
        result = analyze_page_performance(
            url="http://example.com",
            html_size=600000,
            visible_text="x",
        )
        assert result.performance_score < 1.0

    def test_deterministic(self):
        kwargs = dict(url="http://example.com", html_size=50000, visible_text="hello world")
        r1 = analyze_page_performance(**kwargs)
        r2 = analyze_page_performance(**kwargs)
        assert r1.performance_score == r2.performance_score
        assert len(r1.findings) == len(r2.findings)

    def test_resource_metrics_built(self):
        result = analyze_page_performance(
            url="http://example.com",
            css_count=3,
            css_total_bytes=9000,
            js_count=2,
            js_total_bytes=5000,
            image_count=5,
            image_total_bytes=20000,
        )
        types = {r.resource_type for r in result.metrics.resource_metrics}
        assert "css" in types
        assert "js" in types
        assert "image" in types
        assert result.metrics.total_resource_count == 10
        assert result.metrics.total_resource_size_bytes == 34000


# ════════════════════════════════════════════════════════════════════════════
# analyze_dataset_performance
# ════════════════════════════════════════════════════════════════════════════


class TestAnalyzeDatasetPerformance:
    def test_empty_dataset(self):
        result = analyze_dataset_performance("ds1", ())
        assert result.dataset_id == "ds1"
        assert result.total_pages == 0

    def test_single_page(self):
        pages = ({"url": "http://example.com", "html_size": 50000},)
        result = analyze_dataset_performance("ds1", pages)
        assert result.total_pages == 1
        assert result.avg_html_size == 50000.0

    def test_multiple_pages(self):
        pages = (
            {"url": "http://a.com", "html_size": 10000},
            {"url": "http://b.com", "html_size": 20000},
            {"url": "http://c.com", "html_size": 30000},
        )
        result = analyze_dataset_performance("ds1", pages)
        assert result.total_pages == 3
        assert result.avg_html_size == 20000.0

    def test_largest_pages_sorted(self):
        pages = (
            {"url": "http://small.com", "html_size": 1000},
            {"url": "http://large.com", "html_size": 100000},
            {"url": "http://medium.com", "html_size": 50000},
        )
        result = analyze_dataset_performance("ds1", pages)
        assert len(result.largest_pages) == 3
        assert result.largest_pages[0] == ("http://large.com", 100000)

    def test_findings_by_severity(self):
        pages = (
            {"url": "http://a.com", "html_size": 200000},
            {"url": "http://b.com", "html_size": 600000},
        )
        result = analyze_dataset_performance("ds1", pages)
        assert result.total_findings > 0
        assert "high" in result.findings_by_severity or "critical" in result.findings_by_severity
