"""Performance Intelligence domain models (Phase 8).

Immutable value objects representing page performance analysis signals
derived from crawled page data.  Captures HTML size, content efficiency,
resource proportions, and optimization opportunities.

These models are provider-neutral and deterministic — they never depend
on browser performance APIs or network timing data.  All metrics are
derived from the static HTML and parsed page content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PerformanceSeverity(StrEnum):
    """Severity classification for performance findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ResourceMetric:
    """Metrics for a single resource (CSS/JS/image) on a page.

    Captures size and type information without coupling to any
    specific browser or rendering engine.
    """

    resource_type: str
    """Resource type: 'css', 'js', 'image', or 'other'."""

    count: int = 0
    """Number of resources of this type."""

    total_size_bytes: int = 0
    """Total size in bytes of all resources of this type."""

    @property
    def avg_size_bytes(self) -> float:
        """Average size per resource of this type."""
        return self.total_size_bytes / self.count if self.count > 0 else 0.0

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError(f"count must be >= 0, got {self.count}")
        if self.total_size_bytes < 0:
            raise ValueError(f"total_size_bytes must be >= 0, got {self.total_size_bytes}")


@dataclass(frozen=True, slots=True)
class PagePerformanceMetrics:
    """Performance metrics derived from a single crawled page.

    All fields are computed deterministically from the page's HTML
    size, parsed content, and resource information.
    """

    url: str
    """URL of the analyzed page."""

    html_size_bytes: int = 0
    """Size of the HTML document in bytes."""

    visible_text_length: int = 0
    """Length of visible text content (characters)."""

    content_efficiency: float = 0.0
    """Ratio of visible text length to HTML size (0.0-1.0).

    Higher values indicate more efficient content-to-markup ratio.
    """

    resource_metrics: tuple[ResourceMetric, ...] = ()
    """Per-type resource metrics (css, js, image, other)."""

    total_resource_count: int = 0
    """Total number of resources referenced."""

    total_resource_size_bytes: int = 0
    """Total size of all resources in bytes."""

    heading_count: int = 0
    """Number of heading tags (h1-h6)."""

    link_count: int = 0
    """Number of links (internal + external)."""

    image_count: int = 0
    """Number of images."""

    images_without_alt: int = 0
    """Number of images missing alt text."""

    inline_css_ratio: float = 0.0
    """Ratio of inline CSS to total CSS (0.0-1.0)."""

    inline_js_ratio: float = 0.0
    """Ratio of inline JS to total JS (0.0-1.0)."""

    def __post_init__(self) -> None:
        if self.html_size_bytes < 0:
            raise ValueError(f"html_size_bytes must be >= 0, got {self.html_size_bytes}")
        if not 0.0 <= self.content_efficiency <= 1.0:
            raise ValueError(
                f"content_efficiency must be in [0.0, 1.0], got {self.content_efficiency}"
            )


@dataclass(frozen=True, slots=True)
class PerformanceFinding:
    """A single performance finding/recommendation for a page."""

    metric_name: str
    """Name of the metric that triggered this finding."""

    severity: PerformanceSeverity
    """Severity of the finding."""

    value: float
    """Actual value of the metric."""

    threshold: float
    """Threshold that was exceeded."""

    description: str
    """Human-readable description of the finding."""

    recommendation: str = ""
    """Actionable recommendation to address this finding."""

    url: str = ""
    """URL of the affected page, if page-level finding."""


@dataclass(frozen=True, slots=True)
class PerformanceResult:
    """Complete performance analysis result for a single page."""

    url: str
    metrics: PagePerformanceMetrics
    findings: tuple[PerformanceFinding, ...] = ()
    performance_score: float = 0.0
    """Overall performance score (0.0-1.0, higher is better)."""


@dataclass(frozen=True, slots=True)
class PerformanceDatasetMetrics:
    """Dataset-wide performance aggregate metrics."""

    dataset_id: str
    total_pages: int = 0
    avg_html_size: float = 0.0
    avg_content_efficiency: float = 0.0
    avg_performance_score: float = 0.0
    pages_above_threshold: int = 0
    """Pages with performance_score >= 0.7."""
    pages_below_threshold: int = 0
    """Pages with performance_score < 0.4."""
    total_findings: int = 0
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    largest_pages: tuple[tuple[str, int], ...] = ()
    """Top 10 largest pages by HTML size (url, size)."""
    least_efficient: tuple[tuple[str, float], ...] = ()
    """Top 10 least efficient pages (url, efficiency)."""


__all__ = [
    "PagePerformanceMetrics",
    "PerformanceDatasetMetrics",
    "PerformanceFinding",
    "PerformanceResult",
    "PerformanceSeverity",
    "ResourceMetric",
]
