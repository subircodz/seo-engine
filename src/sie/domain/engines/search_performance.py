"""Performance Intelligence engine — deterministic analysis (Phase 8).

Pure functions analyzing page performance characteristics from crawled data.
No I/O, no network, no browser APIs.  Same input always yields the same output.

All metrics are derived from:
- HTML document size
- Parsed content structure (headings, links, images, resources)
- Content efficiency ratios
- Resource proportion analysis

Do not pretend to measure Core Web Vitals or real browser performance.
These are static analysis signals only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sie.domain.models.search_performance import (
    PagePerformanceMetrics,
    PerformanceDatasetMetrics,
    PerformanceFinding,
    PerformanceResult,
    PerformanceSeverity,
    ResourceMetric,
)

__all__ = [
    "analyze_dataset_performance",
    "analyze_page_performance",
]


# ── Thresholds ────────────────────────────────────────────────────────

_LARGE_HTML_BYTES = 100_000
_VERY_LARGE_HTML_BYTES = 500_000
_LOW_CONTENT_EFFICIENCY = 0.3
_MIN_CONTENT_EFFICIENCY = 0.1
_MAX_HEADING_COUNT = 50
_MIN_HEADING_COUNT = 1
_MAX_LINK_COUNT = 500
_MAX_RESOURCE_COUNT = 100
_PERFORMANCE_GOOD_THRESHOLD = 0.7
_PERFORMANCE_POOR_THRESHOLD = 0.4


@dataclass(frozen=True)
class _PageInput:
    """Internal input container for page analysis.

    This abstraction allows the engine to work with various page
    representations without coupling to a specific model.
    """

    url: str
    html_size: int = 0
    visible_text: str = ""
    heading_count: int = 0
    link_count: int = 0
    image_count: int = 0
    images_without_alt: int = 0
    css_count: int = 0
    css_total_bytes: int = 0
    js_count: int = 0
    js_total_bytes: int = 0
    image_total_bytes: int = 0
    inline_css_bytes: int = 0
    inline_js_bytes: int = 0


def analyze_page_performance(
    url: str,
    html_size: int = 0,
    visible_text: str = "",
    heading_count: int = 0,
    link_count: int = 0,
    image_count: int = 0,
    images_without_alt: int = 0,
    css_count: int = 0,
    css_total_bytes: int = 0,
    js_count: int = 0,
    js_total_bytes: int = 0,
    image_total_bytes: int = 0,
    inline_css_bytes: int = 0,
    inline_js_bytes: int = 0,
) -> PerformanceResult:
    """Analyze performance characteristics of a single page.

    All parameters are optional to accommodate varying data availability.
    Missing data simply results in neutral metrics.

    Returns a PerformanceResult with metrics, findings, and a score.
    """
    page = _PageInput(
        url=url,
        html_size=html_size,
        visible_text=visible_text,
        heading_count=heading_count,
        link_count=link_count,
        image_count=image_count,
        images_without_alt=images_without_alt,
        css_count=css_count,
        css_total_bytes=css_total_bytes,
        js_count=js_count,
        js_total_bytes=js_total_bytes,
        image_total_bytes=image_total_bytes,
        inline_css_bytes=inline_css_bytes,
        inline_js_bytes=inline_js_bytes,
    )

    metrics = _calculate_metrics(page)
    findings = _detect_findings(page, metrics)
    score = _calculate_score(metrics, findings)

    return PerformanceResult(
        url=url,
        metrics=metrics,
        findings=tuple(findings),
        performance_score=score,
    )


def _calculate_metrics(page: _PageInput) -> PagePerformanceMetrics:
    """Calculate deterministic performance metrics from page data."""
    text_len = len(page.visible_text)
    content_efficiency = (
        min(text_len / page.html_size, 1.0) if page.html_size > 0 else 0.0
    )

    resource_metrics = _build_resource_metrics(page)
    total_resources = page.css_count + page.js_count + page.image_count
    total_resource_size = page.css_total_bytes + page.js_total_bytes + page.image_total_bytes

    inline_css_ratio = (
        page.inline_css_bytes / page.css_total_bytes
        if page.css_total_bytes > 0
        else 0.0
    )
    inline_js_ratio = (
        page.inline_js_bytes / page.js_total_bytes
        if page.js_total_bytes > 0
        else 0.0
    )

    return PagePerformanceMetrics(
        url=page.url,
        html_size_bytes=page.html_size,
        visible_text_length=text_len,
        content_efficiency=round(content_efficiency, 4),
        resource_metrics=tuple(resource_metrics),
        total_resource_count=total_resources,
        total_resource_size_bytes=total_resource_size,
        heading_count=page.heading_count,
        link_count=page.link_count,
        image_count=page.image_count,
        images_without_alt=page.images_without_alt,
        inline_css_ratio=round(inline_css_ratio, 4),
        inline_js_ratio=round(inline_js_ratio, 4),
    )


def _build_resource_metrics(page: _PageInput) -> list[ResourceMetric]:
    """Build per-type resource metrics."""
    metrics = []
    if page.css_count > 0:
        metrics.append(
            ResourceMetric(
                resource_type="css",
                count=page.css_count,
                total_size_bytes=page.css_total_bytes,
            )
        )
    if page.js_count > 0:
        metrics.append(
            ResourceMetric(
                resource_type="js",
                count=page.js_count,
                total_size_bytes=page.js_total_bytes,
            )
        )
    if page.image_count > 0:
        metrics.append(
            ResourceMetric(
                resource_type="image",
                count=page.image_count,
                total_size_bytes=page.image_total_bytes,
            )
        )
    return metrics


def _detect_findings(
    page: _PageInput, metrics: PagePerformanceMetrics
) -> list[PerformanceFinding]:
    """Detect performance findings based on thresholds."""
    findings: list[PerformanceFinding] = []

    # HTML size findings
    if page.html_size >= _VERY_LARGE_HTML_BYTES:
        findings.append(
            PerformanceFinding(
                metric_name="html_size",
                severity=PerformanceSeverity.CRITICAL,
                value=float(page.html_size),
                threshold=float(_VERY_LARGE_HTML_BYTES),
                description=(
                    f"HTML document is very large "
                    f"({page.html_size:,} bytes). "
                    f"May cause slow parsing and rendering."
                ),
                recommendation=(
                    "Reduce HTML size by minifying markup, removing "
                    "unused code, and implementing server-side rendering "
                    "or code splitting."
                ),
                url=page.url,
            )
        )
    elif page.html_size >= _LARGE_HTML_BYTES:
        findings.append(
            PerformanceFinding(
                metric_name="html_size",
                severity=PerformanceSeverity.HIGH,
                value=float(page.html_size),
                threshold=float(_LARGE_HTML_BYTES),
                description=(
                    f"HTML document is large "
                    f"({page.html_size:,} bytes)."
                ),
                recommendation="Consider minifying HTML and removing unnecessary markup.",
                url=page.url,
            )
        )

    # Content efficiency findings
    if page.html_size > 0:
        if metrics.content_efficiency < _MIN_CONTENT_EFFICIENCY:
            findings.append(
                PerformanceFinding(
                    metric_name="content_efficiency",
                    severity=PerformanceSeverity.CRITICAL,
                    value=metrics.content_efficiency,
                    threshold=_MIN_CONTENT_EFFICIENCY,
                    description=(
                        f"Content efficiency is critically low "
                        f"({metrics.content_efficiency:.2%}). "
                        f"Very little visible text relative to HTML size."
                    ),
                    recommendation=(
                        "Reduce bloated markup, remove inline scripts/styles, "
                        "and ensure meaningful content is not buried in markup."
                    ),
                    url=page.url,
                )
            )
        elif metrics.content_efficiency < _LOW_CONTENT_EFFICIENCY:
            findings.append(
                PerformanceFinding(
                    metric_name="content_efficiency",
                    severity=PerformanceSeverity.HIGH,
                    value=metrics.content_efficiency,
                    threshold=_LOW_CONTENT_EFFICIENCY,
                    description=(
                        f"Content efficiency is low "
                        f"({metrics.content_efficiency:.2%}). "
                        f"Significant markup overhead detected."
                    ),
                    recommendation="Reduce markup overhead and improve content-to-markup ratio.",
                    url=page.url,
                )
            )

    # Resource count findings
    if metrics.total_resource_count >= _MAX_RESOURCE_COUNT:
        findings.append(
            PerformanceFinding(
                metric_name="resource_count",
                severity=PerformanceSeverity.HIGH,
                value=float(metrics.total_resource_count),
                threshold=float(_MAX_RESOURCE_COUNT),
                description=(
                    f"Page references {metrics.total_resource_count} resources. "
                    f"High resource count increases HTTP requests."
                ),
                recommendation=(
                    "Bundle and reduce the number of CSS/JS files. "
                    "Use sprites or lazy loading for images."
                ),
                url=page.url,
            )
        )

    # Image optimization findings
    if page.images_without_alt > 0:
        severity = (
            PerformanceSeverity.MEDIUM
            if page.images_without_alt < 5
            else PerformanceSeverity.HIGH
        )
        findings.append(
            PerformanceFinding(
                metric_name="images_without_alt",
                severity=severity,
                value=float(page.images_without_alt),
                threshold=0.0,
                description=(
                    f"{page.images_without_alt} image(s) missing alt text. "
                    f"Affects both accessibility and SEO."
                ),
                recommendation="Add descriptive alt text to all images.",
                url=page.url,
            )
        )

    # Inline resource ratio findings
    if metrics.inline_css_ratio > 0.8 and page.css_count > 0:
        findings.append(
            PerformanceFinding(
                metric_name="inline_css_ratio",
                severity=PerformanceSeverity.MEDIUM,
                value=metrics.inline_css_ratio,
                threshold=0.8,
                description=(
                    f"High inline CSS ratio ({metrics.inline_css_ratio:.0%}). "
                    f"May prevent caching and increase document size."
                ),
                recommendation="Extract inline CSS to external stylesheets.",
                url=page.url,
            )
        )

    if metrics.inline_js_ratio > 0.8 and page.js_count > 0:
        findings.append(
            PerformanceFinding(
                metric_name="inline_js_ratio",
                severity=PerformanceSeverity.MEDIUM,
                value=metrics.inline_js_ratio,
                threshold=0.8,
                description=(
                    f"High inline JS ratio ({metrics.inline_js_ratio:.0%}). "
                    f"May prevent caching and block parsing."
                ),
                recommendation="Extract inline JS to external files and use async/defer loading.",
                url=page.url,
            )
        )

    return findings


def _calculate_score(
    metrics: PagePerformanceMetrics, findings: list[PerformanceFinding]
) -> float:
    """Calculate deterministic performance score (0.0-1.0, higher is better).

    Starts at 1.0 and deducts points for negative findings based on severity.
    """
    score = 1.0

    for finding in findings:
        if finding.severity == PerformanceSeverity.CRITICAL:
            score -= 0.3
        elif finding.severity == PerformanceSeverity.HIGH:
            score -= 0.15
        elif finding.severity == PerformanceSeverity.MEDIUM:
            score -= 0.05
        elif finding.severity == PerformanceSeverity.LOW:
            score -= 0.02

    return round(max(0.0, min(1.0, score)), 2)


def analyze_dataset_performance(
    dataset_id: str,
    pages: tuple[dict[str, Any], ...],
) -> PerformanceDatasetMetrics:
    """Analyze performance across a dataset of pages.

    Each page dict should contain:
    - 'url': str
    - 'html_size': int (optional)
    - 'visible_text': str (optional)
    - 'heading_count': int (optional)
    - 'link_count': int (optional)
    - 'image_count': int (optional)
    - 'images_without_alt': int (optional)
    - 'css_count', 'css_total_bytes': int (optional)
    - 'js_count', 'js_total_bytes': int (optional)
    - 'image_total_bytes': int (optional)
    - 'inline_css_bytes', 'inline_js_bytes': int (optional)

    Returns dataset-level aggregate metrics.
    """
    if not pages:
        return PerformanceDatasetMetrics(dataset_id=dataset_id)

    results: list[PerformanceResult] = []
    for page_data in pages:
        result = analyze_page_performance(
            url=page_data.get("url", ""),
            html_size=page_data.get("html_size", 0),
            visible_text=page_data.get("visible_text", ""),
            heading_count=page_data.get("heading_count", 0),
            link_count=page_data.get("link_count", 0),
            image_count=page_data.get("image_count", 0),
            images_without_alt=page_data.get("images_without_alt", 0),
            css_count=page_data.get("css_count", 0),
            css_total_bytes=page_data.get("css_total_bytes", 0),
            js_count=page_data.get("js_count", 0),
            js_total_bytes=page_data.get("js_total_bytes", 0),
            image_total_bytes=page_data.get("image_total_bytes", 0),
            inline_css_bytes=page_data.get("inline_css_bytes", 0),
            inline_js_bytes=page_data.get("inline_js_bytes", 0),
        )
        results.append(result)

    total = len(results)
    avg_html = sum(r.metrics.html_size_bytes for r in results) / total
    avg_efficiency = sum(r.metrics.content_efficiency for r in results) / total
    avg_score = sum(r.performance_score for r in results) / total

    above = sum(1 for r in results if r.performance_score >= _PERFORMANCE_GOOD_THRESHOLD)
    below = sum(1 for r in results if r.performance_score < _PERFORMANCE_POOR_THRESHOLD)

    # Aggregate findings by severity
    findings_by_severity: dict[str, int] = {}
    total_findings = 0
    for r in results:
        for f in r.findings:
            total_findings += 1
            sev = f.severity.value
            findings_by_severity[sev] = findings_by_severity.get(sev, 0) + 1

    # Top 10 largest pages
    sorted_by_size = sorted(results, key=lambda r: r.metrics.html_size_bytes, reverse=True)
    largest = tuple(
        (r.url, r.metrics.html_size_bytes) for r in sorted_by_size[:10]
    )

    # Top 10 least efficient
    with_efficiency = [
        r for r in results if r.metrics.html_size_bytes > 0
    ]
    sorted_by_eff = sorted(with_efficiency, key=lambda r: r.metrics.content_efficiency)
    least_eff = tuple(
        (r.url, r.metrics.content_efficiency) for r in sorted_by_eff[:10]
    )

    return PerformanceDatasetMetrics(
        dataset_id=dataset_id,
        total_pages=total,
        avg_html_size=round(avg_html, 1),
        avg_content_efficiency=round(avg_efficiency, 4),
        avg_performance_score=round(avg_score, 2),
        pages_above_threshold=above,
        pages_below_threshold=below,
        total_findings=total_findings,
        findings_by_severity=findings_by_severity,
        largest_pages=largest,
        least_efficient=least_eff,
    )
