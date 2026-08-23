"""Audit service: orchestrates Technical SEO + Link Graph engines.

Results are cached in-memory keyed by ``run_id``.  This is intentionally thin:
the service fetches crawl data, parses pages via the ``PageParser`` port, runs
the deterministic engines, and stores the result.
"""

from __future__ import annotations

from sie.domain.engines.link_graph import build_architecture_report
from sie.domain.engines.technical_seo import run_technical_audit
from sie.domain.models.audit import (
    LinkExtraction,
    PageDOM,
    SiteArchitectureReport,
    TechnicalAuditResult,
)
from sie.domain.models.page import FetchedPage
from sie.domain.ports.parsing import PageParser
from sie.domain.ports.persistence import CrawlRunRepository
from sie.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    def __init__(self, repository: CrawlRunRepository, parser: PageParser) -> None:
        self._repository = repository
        self._parser = parser
        self._technical_results: dict[str, TechnicalAuditResult] = {}
        self._architecture_reports: dict[str, SiteArchitectureReport] = {}

    # ── parsing helpers ──────────────────────────────────────────────────────

    def _parse_pages(
        self, crawled_pages: list[FetchedPage]
    ) -> tuple[dict[str, PageDOM], dict[str, LinkExtraction]]:
        parsed: dict[str, PageDOM] = {}
        extractions: dict[str, LinkExtraction] = {}
        for page in crawled_pages:
            parsed[page.url] = self._parser.parse_page(page)
            extractions[page.url] = self._parser.parse_links(page)
        return parsed, extractions

    # ── Technical SEO ────────────────────────────────────────────────────────

    async def run_technical_audit(
        self,
        run_id: str,
        crawled_pages: list[FetchedPage],
        priorities: set[str] | None = None,
    ) -> TechnicalAuditResult:
        parsed, extractions = self._parse_pages(crawled_pages)
        result = run_technical_audit(
            list(parsed.values()), link_extractions=extractions, priorities=priorities
        )
        self._technical_results[run_id] = result
        logger.info(
            "technical audit for %s: %d issues (%d critical, %d warning, %d info)",
            run_id,
            result.total_issues,
            result.critical_count,
            result.warning_count,
            result.info_count,
        )
        return result

    def get_technical_result(self, run_id: str) -> TechnicalAuditResult | None:
        return self._technical_results.get(run_id)

    # ── Link graph ───────────────────────────────────────────────────────────

    async def run_link_graph(
        self,
        run_id: str,
        crawled_pages: list[FetchedPage],
        *,
        max_depth: int = 10,
        damping: float = 0.85,
        max_iterations: int = 100,
        thin_threshold: int = 2,
    ) -> SiteArchitectureReport:
        _, extractions = self._parse_pages(crawled_pages)
        report = build_architecture_report(
            crawled_pages,
            extractions,
            max_depth_for_analysis=max_depth,
            pagerank_damping=damping,
            pagerank_max_iterations=max_iterations,
            orphan_threshold=thin_threshold,
        )
        self._architecture_reports[run_id] = report
        logger.info(
            "link graph for %s: %d pages, %d internal links, depth avg %.1f",
            run_id,
            report.total_pages,
            report.total_internal_links,
            report.avg_depth,
        )
        return report

    def get_architecture_report(self, run_id: str) -> SiteArchitectureReport | None:
        return self._architecture_reports.get(run_id)
