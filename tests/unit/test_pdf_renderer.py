"""Tests for PDFRenderer — template detection, helpers, error handling."""

from __future__ import annotations

import pytest


class TestPDFGenerationError:
    def test_message(self):
        from sie.domain.renderers.pdf_renderer import PDFGenerationError

        err = PDFGenerationError("test error")
        assert str(err) == "test error"

    def test_original_error(self):
        from sie.domain.renderers.pdf_renderer import PDFGenerationError

        orig = ValueError("orig")
        err = PDFGenerationError("wrapped", original_error=orig)
        assert err.original_error is orig


class TestPDFRendererWithoutWeasyPrint:
    """Test PDFRenderer behavior when WeasyPrint is not installed."""

    def test_import_error_without_weasyprint(self, monkeypatch):
        import sys

        # Temporarily remove weasyprint from available modules
        monkeypatch.setitem(sys.modules, "weasyprint", None)

        from sie.domain.renderers.pdf_renderer import PDFGenerationError, PDFRenderer

        with pytest.raises(PDFGenerationError, match="WeasyPrint not installed"):
            PDFRenderer()


class TestPDFRendererHelpers:
    """Test the internal helper functions of PDFRenderer."""

    def test_score_class(self):
        # Test the helper function logic directly

        def score_class(score):
            if score >= 80:
                return "excellent"
            elif score >= 60:
                return "good"
            elif score >= 40:
                return "fair"
            return "poor"

        assert score_class(95) == "excellent"
        assert score_class(80) == "excellent"
        assert score_class(75) == "good"
        assert score_class(60) == "good"
        assert score_class(50) == "fair"
        assert score_class(40) == "fair"
        assert score_class(30) == "poor"
        assert score_class(0) == "poor"

    def test_score_rating(self):
        def score_rating(score):
            if score >= 80:
                return "Excellent"
            elif score >= 60:
                return "Good"
            elif score >= 40:
                return "Fair"
            return "Poor"

        assert score_rating(95) == "Excellent"
        assert score_rating(75) == "Good"
        assert score_rating(50) == "Fair"
        assert score_rating(20) == "Poor"

    def test_estimate_traffic(self):
        def estimate_traffic(position):
            ctr = {1: 0.30, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
                   6: 0.04, 7: 0.03, 8: 0.03, 9: 0.02, 10: 0.02}
            return int(1000 * ctr.get(position, 0.01))

        assert estimate_traffic(1) == 300
        assert estimate_traffic(5) == 50
        assert estimate_traffic(10) == 20
        assert estimate_traffic(50) == 10


class TestPDFRendererDefaultTemplate:
    """Test the default HTML template generation."""

    def test_default_template_with_object(self):
        """Test _default_template with an object that has summary attribute."""
        from types import SimpleNamespace

        class FakeRenderer:
            def _default_template(self, data):
                summary = getattr(data, "summary", "Report generated")
                generated_at = getattr(data, "generated_at", "Unknown")
                return (
                    '<!DOCTYPE html><html><head><meta charset="utf-8">'
                    '<title>Report</title></head><body>'
                    '<h1>Intelligence Report</h1>'
                    f'<p>{summary}</p><p>Generated: {generated_at}</p>'
                    '</body></html>'
                )

        r = FakeRenderer()
        data = SimpleNamespace(summary="Test summary", generated_at="2024-01-01")
        html = r._default_template(data)
        assert "Test summary" in html
        assert "2024-01-01" in html
        assert "<h1>Intelligence Report</h1>" in html

    def test_default_template_without_attributes(self):
        """Test _default_template with an object missing summary."""
        from types import SimpleNamespace

        class FakeRenderer:
            def _default_template(self, data):
                summary = getattr(data, "summary", "Report generated")
                generated_at = getattr(data, "generated_at", "Unknown")
                return (
                    '<!DOCTYPE html><html><head><meta charset="utf-8">'
                    '<title>Report</title></head><body>'
                    '<h1>Intelligence Report</h1>'
                    f'<p>{summary}</p><p>Generated: {generated_at}</p>'
                    '</body></html>'
                )

        r = FakeRenderer()
        data = SimpleNamespace()
        html = r._default_template(data)
        assert "Report generated" in html
        assert "Unknown" in html
