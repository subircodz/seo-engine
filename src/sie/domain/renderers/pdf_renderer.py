"""PDF Report Renderer — converts structured reports to professional PDFs.

Part of Phase 12D: PDF export for consolidated intelligence reports.

Uses WeasyPrint for HTML-to-PDF conversion with professional styling.
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
from typing import Any

from jinja2 import Environment

__all__ = ["PDFGenerationError", "PDFRenderer"]

logger = logging.getLogger(__name__)


class PDFGenerationError(Exception):
    """Raised when PDF generation fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class PDFRenderer:
    """Render intelligence reports to professional PDF format.

    Uses WeasyPrint for HTML-to-PDF conversion.
    Supports headers, footers, page numbering, and professional layouts.
    """

    TEMPLATE_DIR = pathlib.Path(__file__).parent.parent.parent / "templates"

    def __init__(self) -> None:
        try:
            import weasyprint

            self._weasyprint = weasyprint
        except ImportError as exc:
            raise PDFGenerationError(
                "WeasyPrint not installed. Install with: pip install weasyprint"
            ) from exc

        self._jinja_env = Environment(autoescape=False)
        # Add custom filters
        self._jinja_env.filters['percentage'] = lambda x: f"{x*100:.1f}%"
        self._jinja_env.filters['number_format'] = lambda x: f"{x:,}"
        self._jinja_env.filters['tojson'] = lambda x: __import__('json').dumps(x, default=str)

    def render(self, report_data: Any) -> bytes:
        """Render a structured report to PDF bytes.

        Args:
            report_data: IntelligenceReport, SiteAnalysisResult, or dict-like object.

        Returns:
            PDF content as bytes.
        """
        html = self._build_html(report_data)
        return self._render_html_sync(html)

    async def render_async(self, report_data: Any) -> bytes:
        """Render a structured report to PDF bytes (async version).

        Offloads the blocking WeasyPrint rendering to a thread pool
        to avoid blocking the event loop.

        Args:
            report_data: IntelligenceReport, SiteAnalysisResult, or dict-like object.

        Returns:
            PDF content as bytes.
        """
        html = self._build_html(report_data)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._render_html_sync, html)

    def _build_html(self, data: Any) -> str:
        """Build HTML from report data using Jinja2 template."""
        # Determine template based on data type
        if hasattr(data, 'domain') and hasattr(data, 'overall_score'):
            # SiteAnalysisResult
            template_path = self.TEMPLATE_DIR / "reports" / "site_analysis.html"
        else:
            # IntelligenceReport or other
            template_path = self.TEMPLATE_DIR / "reports" / "report.html"

        if template_path.exists():
            try:
                template_content = template_path.read_text(encoding="utf-8")
                template = self._jinja_env.from_string(template_content)
                return self._render_template(template, data)
            except Exception as exc:
                logger.warning("Template rendering failed: %s", exc)

        return self._default_template(data)

    def _render_template(self, template, data: Any) -> str:
        """Render a Jinja2 template with report data."""
        # Add helper functions to context
        def score_class(score):
            if score >= 80:
                return "excellent"
            elif score >= 60:
                return "good"
            elif score >= 40:
                return "fair"
            return "poor"

        def score_rating(score):
            if score >= 80:
                return "Excellent"
            elif score >= 60:
                return "Good"
            elif score >= 40:
                return "Fair"
            return "Poor"

        def estimate_traffic(position):
            ctr = {1: 0.30, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05, 6: 0.04, 7: 0.03, 8: 0.03, 9: 0.02, 10: 0.02}
            return int(1000 * ctr.get(position, 0.01))

        context = {
            "score_class": score_class,
            "score_rating": score_rating,
            "estimate_traffic": estimate_traffic,
        }

        # Add data attributes to context
        if hasattr(data, '__dataclass_fields__'):
            # dataclass (including slotted) — use fields()
            import dataclasses
            for f in dataclasses.fields(data):
                if not f.name.startswith('_'):
                    context[f.name] = getattr(data, f.name)
        elif hasattr(data, '__dict__'):
            # Regular object with __dict__
            for key, value in data.__dict__.items():
                if not key.startswith('_'):
                    context[key] = value
        elif isinstance(data, dict):
            context.update(data)

        # Ensure country is in context for PDF header
        if 'country' not in context:
            context['country'] = context.get('country', '')

        # Ensure access_status and website_type are in context
        if 'access_status' not in context:
            context['access_status'] = None
        if 'website_type' not in context:
            context['website_type'] = None
        if 'report_metadata' not in context:
            context['report_metadata'] = None

        return template.render(**context)

    def _extract_findings(self, data: Any) -> list[dict]:
        """Extract findings from report data with evidence sources."""
        findings = []

        if hasattr(data, "findings"):
            for f in data.findings:
                findings.append(
                    {
                        "category": getattr(f, "category", "general"),
                        "severity": getattr(f, "severity", "medium"),
                        "title": getattr(f, "title", ""),
                        "description": getattr(f, "description", ""),
                        "recommendation": getattr(f, "recommendation", ""),
                        "evidence_sources": getattr(f, "evidence_sources", ()),
                    }
                )
        elif isinstance(data, dict):
            for f in data.get("findings", []):
                findings.append(
                    {
                        "category": f.get("category", "general"),
                        "severity": f.get("severity", "medium"),
                        "title": f.get("title", ""),
                        "description": f.get("description", ""),
                        "recommendation": f.get("recommendation", ""),
                        "evidence_sources": f.get("evidence_sources", ()),
                    }
                )

        return findings

    def _extract_recommendations(self, data: Any) -> list[dict]:
        """Extract recommendations from report data."""
        recommendations = []

        if hasattr(data, "recommendations"):
            for r in data.recommendations:
                recommendations.append(
                    {
                        "title": getattr(r, "title", ""),
                        "description": getattr(r, "description", ""),
                        "priority": getattr(r, "priority", 0.5),
                    }
                )
        elif isinstance(data, dict):
            for r in data.get("recommendations", []):
                recommendations.append(
                    {
                        "title": r.get("title", ""),
                        "description": r.get("description", ""),
                        "priority": r.get("priority", 0.5),
                    }
                )

        return recommendations

    def _default_template(self, data: Any) -> str:
        """Generate a minimal HTML template when no template file exists."""
        summary = getattr(data, "summary", "Report generated")
        generated_at = getattr(data, "generated_at", "Unknown")
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Report</title></head>
<body><h1>Intelligence Report</h1><p>{summary}</p><p>Generated: {generated_at}</p></body></html>"""

    def _render_html_sync(self, html: str) -> bytes:
        """Convert HTML string to PDF (synchronous, blocking)."""
        doc = self._weasyprint.HTML(string=html).render()
        return doc.write_pdf()

    def _render_html(self, html: str) -> bytes:
        """Deprecated alias for _render_html_sync."""
        return self._render_html_sync(html)
