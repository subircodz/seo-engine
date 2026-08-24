"""Diagnosis service — orchestrates SEO diagnosis across engines.

Combines signals from Technical SEO, Link Graph, and Content Intelligence
to produce structured diagnosis results.  Results are cached in-memory
keyed by ``run_id``.
"""

from __future__ import annotations

from sie.domain.engines.diagnosis import run_diagnosis
from sie.domain.models.audit import (
    LinkExtraction,
    PageDOM,
    SiteArchitectureReport,
    TechnicalAuditResult,
)
from sie.domain.models.content import ContentMetrics
from sie.domain.models.diagnosis import DiagnosisResult
from sie.domain.models.page import FetchedPage
from sie.domain.ports.parsing import PageParser
from sie.domain.ports.persistence import CrawlRunRepository
from sie.logging import get_logger

logger = get_logger(__name__)


class DiagnosisService:
    """Orchestrates deterministic SEO diagnosis for a crawl run."""

    def __init__(self, repository: CrawlRunRepository, parser: PageParser) -> None:
        self._repository = repository
        self._parser = parser
        self._results: dict[str, DiagnosisResult] = {}

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

    # ── Diagnosis ────────────────────────────────────────────────────────────

    async def run_diagnosis(
        self,
        run_id: str,
        crawled_pages: list[FetchedPage],
        *,
        technical: TechnicalAuditResult | None = None,
        architecture: SiteArchitectureReport | None = None,
        content_metrics: list[ContentMetrics] | None = None,
        priorities: set[str] | None = None,
    ) -> DiagnosisResult:
        """Run deterministic SEO diagnosis.

        If ``technical`` / ``architecture`` / ``content_metrics`` are not
        provided, the service computes them from the crawled pages using the
        existing engines.
        """
        parsed, extractions = self._parse_pages(crawled_pages)

        # Lazily compute missing engine outputs
        if technical is None:
            from sie.domain.engines.technical_seo import run_technical_audit

            technical = run_technical_audit(list(parsed.values()), link_extractions=extractions)

        if architecture is None:
            from sie.domain.engines.link_graph import build_architecture_report

            architecture = build_architecture_report(crawled_pages, extractions)

        if content_metrics is None:
            from sie.domain.engines.content_intelligence import analyze_content_batch

            html_map: dict[str, str] = {}
            for page in crawled_pages:
                if page.is_html:
                    html_map[page.url] = page.decoded_text()
                else:
                    html_map[page.url] = ""
            content_metrics = analyze_content_batch(list(parsed.values()), html_map)

        result = run_diagnosis(
            run_id,
            technical=technical,
            architecture=architecture,
            content_metrics=content_metrics,
            priorities=priorities,
        )

        self._results[run_id] = result
        logger.info(
            "diagnosis for %s: %d issues (P0=%d, P1=%d, P2=%d, P3=%d)",
            run_id,
            result.total_issues,
            result.issues_by_priority.get("P0", 0),
            result.issues_by_priority.get("P1", 0),
            result.issues_by_priority.get("P2", 0),
            result.issues_by_priority.get("P3", 0),
        )
        return result

    def get_result(self, run_id: str) -> DiagnosisResult | None:
        return self._results.get(run_id)
