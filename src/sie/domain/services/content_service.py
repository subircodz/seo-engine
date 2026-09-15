"""Content Service — orchestrates content analysis and persistence.

Depends on PageParser port and CrawlRunRepository. No FastAPI, no DB logic here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sie.domain.engines.content_comparison import find_duplicate_groups
from sie.domain.engines.content_intelligence import analyze_content_batch
from sie.domain.models.audit import PageDOM
from sie.domain.models.content import (
    ContentAnalysisConfig,
    ContentComparison,
    ContentMetrics,
    ContentQualityReport,
    QualityTier,
)
from sie.domain.models.page import FetchedPage
from sie.domain.ports.parsing import PageParser
from sie.domain.ports.persistence import CrawlRunRepository
from sie.logging import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ContentService:
    """Orchestrates content analysis for a crawl run."""

    def __init__(
        self,
        repository: CrawlRunRepository,
        parser: PageParser,
    ) -> None:
        self._repository = repository
        self._parser = parser
        self._analysis_cache: dict[str, list[ContentMetrics]] = {}
        self._comparison_cache: dict[str, list[ContentComparison]] = {}
        self._quality_cache: dict[str, ContentQualityReport] = {}

    def _build_html_map(self, crawled_pages: list[FetchedPage]) -> dict[str, str]:
        """Build URL -> HTML content mapping from fetched pages."""
        html_map = {}
        for page in crawled_pages:
            if page.is_html:
                html_map[page.url] = page.decoded_text()
            else:
                html_map[page.url] = ""
        return html_map

    async def analyze_content(
        self,
        run_id: str,
        crawled_pages: list[FetchedPage],
        config: ContentAnalysisConfig | None = None,
    ) -> list[ContentMetrics]:
        """Analyze content for all pages in a crawl run."""
        config = config or ContentAnalysisConfig()

        parsed_pages: list[PageDOM] = []
        for page in crawled_pages:
            parsed = self._parser.parse_page(page)
            parsed_pages.append(parsed)

        html_map = self._build_html_map(crawled_pages)
        metrics = analyze_content_batch(parsed_pages, html_map, config)

        self._analysis_cache[run_id] = metrics
        logger.info(
            "content analysis for %s: %d pages analyzed, avg quality %.1f",
            run_id,
            len(metrics),
            sum(m.quality_score for m in metrics) / len(metrics) if metrics else 0,
        )
        return metrics

    def get_analysis(self, run_id: str) -> list[ContentMetrics] | None:
        return self._analysis_cache.get(run_id)

    async def run_comparison(
        self,
        run_id: str,
        metrics: list[ContentMetrics] | None = None,
        config: ContentAnalysisConfig | None = None,
    ) -> list[ContentComparison]:
        """Run pairwise duplicate/near-duplicate detection."""
        config = config or ContentAnalysisConfig()
        metrics = metrics or self._analysis_cache.get(run_id, [])

        if len(metrics) < 2:
            return []

        duplicate_groups = find_duplicate_groups(
            metrics,
            near_threshold=config.near_duplicate_threshold,
            exact_threshold=config.duplicate_similarity_threshold,
        )

        comparisons: list[ContentComparison] = []
        for group in duplicate_groups:
            if len(group) < 2:
                continue
            base = next(m for m in metrics if m.url == group[0])
            for url in group[1:]:
                other = next(m for m in metrics if m.url == url)
                cmp = self._compare_two(base, other, config)
                comparisons.append(cmp)

        self._comparison_cache[run_id] = comparisons
        logger.info(
            "content comparison for %s: %d duplicate groups found",
            run_id,
            len(duplicate_groups),
        )
        return comparisons

    def _compare_two(
        self,
        a: ContentMetrics,
        b: ContentMetrics,
        config: ContentAnalysisConfig,
    ) -> ContentComparison:
        from sie.domain.engines.content_comparison import compare_content

        return compare_content(
            a,
            b,
            exact_threshold=config.duplicate_similarity_threshold,
            near_threshold=config.near_duplicate_threshold,
        )

    def get_comparisons(self, run_id: str) -> list[ContentComparison] | None:
        return self._comparison_cache.get(run_id)

    async def generate_quality_report(
        self,
        run_id: str,
        metrics: list[ContentMetrics] | None = None,
    ) -> ContentQualityReport:
        """Generate aggregated quality report for a crawl run."""
        metrics = metrics or self._analysis_cache.get(run_id, [])

        if not metrics:
            return ContentQualityReport(
                run_id=run_id,
                total_pages=0,
                analyzed_pages=0,
                avg_quality_score=0.0,
                quality_distribution={tier: 0 for tier in QualityTier},
                thin_content_pages=(),
                duplicate_groups=(),
                top_issues=(),
            )

        total = len(metrics)
        avg_score = sum(m.quality_score for m in metrics) / total

        distribution: dict[QualityTier, int] = {tier: 0 for tier in QualityTier}
        thin_pages: list[str] = []
        issue_counter: dict[str, int] = {}

        for m in metrics:
            distribution[m.quality_tier] += 1
            if m.thin_content:
                thin_pages.append(m.url)
            if m.headings.h1_count == 0:
                issue_counter["missing_h1"] = issue_counter.get("missing_h1", 0) + 1
            if m.images.missing_alt_percentage > 50:
                issue_counter["missing_alt_text"] = issue_counter.get("missing_alt_text", 0) + 1
            if m.links.internal_links < 2:
                issue_counter["low_internal_links"] = issue_counter.get("low_internal_links", 0) + 1
            if m.readability.flesch_reading_ease < 30:
                issue_counter["poor_readability"] = issue_counter.get("poor_readability", 0) + 1
            if m.keywords.keyword_stuffing_score > 0.05:
                issue_counter["keyword_stuffing"] = issue_counter.get("keyword_stuffing", 0) + 1
            if m.freshness.is_stale:
                issue_counter["stale_content"] = issue_counter.get("stale_content", 0) + 1
            if not m.structured_data.has_schema_org:
                issue_counter["missing_schema"] = issue_counter.get("missing_schema", 0) + 1

        duplicate_groups = find_duplicate_groups(metrics)
        dup_urls = [tuple(g) for g in duplicate_groups]

        top_issues = tuple(sorted(issue_counter.items(), key=lambda x: -x[1])[:10])

        report = ContentQualityReport(
            run_id=run_id,
            total_pages=total,
            analyzed_pages=total,
            # ContentMetrics.quality_score is 0-100; the aggregated report
            # contract is normalized to 0-1 for downstream scoring/rendering.
            avg_quality_score=round(avg_score / 100, 4),
            quality_distribution=distribution,
            thin_content_pages=tuple(thin_pages),
            duplicate_groups=tuple(dup_urls),
            top_issues=top_issues,
        )

        self._quality_cache[run_id] = report
        logger.info(
            "quality report for %s: avg score %.1f, thin=%d, dups=%d",
            run_id,
            avg_score,
            len(thin_pages),
            len(dup_urls),
        )
        return report

    def get_quality_report(self, run_id: str) -> ContentQualityReport | None:
        return self._quality_cache.get(run_id)

    async def get_page_metrics(self, run_id: str, url: str) -> ContentMetrics | None:
        metrics = self._analysis_cache.get(run_id, [])
        for m in metrics:
            if m.url == url:
                return m
        return None

    async def get_pages_by_type(
        self,
        run_id: str,
        content_type: str,
    ) -> list[ContentMetrics]:
        metrics = self._analysis_cache.get(run_id, [])
        return [m for m in metrics if m.content_type.value == content_type]

    async def get_pages_by_quality(
        self,
        run_id: str,
        quality_tier: QualityTier,
    ) -> list[ContentMetrics]:
        metrics = self._analysis_cache.get(run_id, [])
        return [m for m in metrics if m.quality_tier == quality_tier]
