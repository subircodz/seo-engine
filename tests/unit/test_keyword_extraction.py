"""Regression tests for keyword extraction — ensures HTML artifacts and URL
fragments do not leak into the target keyword list."""

from __future__ import annotations

from sie.domain.services.site_analysis import SiteAnalysisService

# ════════════════════════════════════════════════════════════════════════════
# _strip_html_for_keywords
# ════════════════════════════════════════════════════════════════════════════


class TestStripHtmlForKeywords:
    """Verify the HTML-stripping helper removes markup before keyword extraction."""

    def test_html_entities_decoded(self):
        html = "<p>This is &quot;important&quot; content &amp; more</p>"
        result = SiteAnalysisService._strip_html_for_keywords(html)
        assert "&quot;" not in result
        assert "&amp;" not in result
        assert "important" in result
        assert "content" in result

    def test_script_tags_removed(self):
        html = '<p>Hello world</p><script>var x = "malicious";</script><p>More text</p>'
        result = SiteAnalysisService._strip_html_for_keywords(html)
        assert "malicious" not in result
        assert "Hello" in result
        assert "world" in result

    def test_style_tags_removed(self):
        html = "<p>Actual content</p><style>.foo { color: red; }</style>"
        result = SiteAnalysisService._strip_html_for_keywords(html)
        assert "foo" not in result or "foo" in "Actual content"
        assert "Actual" in result
        assert "content" in result

    def test_noscript_tags_removed(self):
        html = "<p>Content</p><noscript>Please enable JavaScript</noscript>"
        result = SiteAnalysisService._strip_html_for_keywords(html)
        assert "enable" not in result
        assert "Content" in result

    def test_bare_urls_removed(self):
        html = "Check out https://example.com/path for more info"
        result = SiteAnalysisService._strip_html_for_keywords(html)
        assert "https" not in result.split()
        assert "example.com" not in result

    def test_email_addresses_removed(self):
        html = "Contact us at info@example.com for details"
        result = SiteAnalysisService._strip_html_for_keywords(html)
        assert "info@example.com" not in result

    def test_numeric_only_not_extracted_as_keyword(self):
        """Numeric-only tokens should not become keywords (regex requires leading letter)."""
        svc_obj = object.__new__(SiteAnalysisService)
        from unittest.mock import MagicMock

        svc_obj._crawl_service = MagicMock()
        svc_obj._audit_service = MagicMock()
        svc_obj._content_service = MagicMock()
        svc_obj._search_provider = MagicMock()
        svc_obj._repository = MagicMock()
        svc_obj._crux_service = None
        svc_obj._collection_service = MagicMock()
        svc_obj._intelligence_service = MagicMock()
        html = "<p>Page 42 shows 2024 data with good content</p>" * 10
        pages = [_FakePage(html)]
        keywords = svc_obj._extract_target_keywords(pages, max_keywords=50)
        for kw in keywords:
            assert kw not in ("42", "2024"), f"Numeric token in keywords: {kw}"

    def test_complex_mixed_html(self):
        """Realistic HTML with entities, tags, and content."""
        html = (
            '<div class="header">&quot;SEO &amp; Marketing&quot;</div>'
            '<p>Best practices for <a href="https://example.com">search engines</a></p>'
            '<script>track("pageview");</script>'
            "<p>Another paragraph with content</p>"
        )
        result = SiteAnalysisService._strip_html_for_keywords(html)
        assert "quot" not in result.lower().split()
        assert "Marketing" in result or "marketing" in result.lower()
        assert "SEO" in result or "seo" in result.lower()
        assert "search" in result
        assert "engines" in result


# ════════════════════════════════════════════════════════════════════════════
# _is_url_or_domain_token
# ════════════════════════════════════════════════════════════════════════════


class TestIsUrlOrDomainToken:
    """Verify URL/domain fragment detection."""

    def test_protocol_prefixes_rejected(self):
        assert SiteAnalysisService._is_url_or_domain_token("http")
        assert SiteAnalysisService._is_url_or_domain_token("https")
        assert SiteAnalysisService._is_url_or_domain_token("ftp")

    def test_tld_tokens_rejected(self):
        assert SiteAnalysisService._is_url_or_domain_token("com")
        assert SiteAnalysisService._is_url_or_domain_token("org")
        assert SiteAnalysisService._is_url_or_domain_token("net")
        assert SiteAnalysisService._is_url_or_domain_token("io")

    def test_html_tokens_rejected(self):
        assert SiteAnalysisService._is_url_or_domain_token("html")
        assert SiteAnalysisService._is_url_or_domain_token("php")
        assert SiteAnalysisService._is_url_or_domain_token("css")

    def test_normal_words_accepted(self):
        assert not SiteAnalysisService._is_url_or_domain_token("marketing")
        assert not SiteAnalysisService._is_url_or_domain_token("business")
        assert not SiteAnalysisService._is_url_or_domain_token("strategy")

    def test_single_numeric_rejected(self):
        assert SiteAnalysisService._is_url_or_domain_token("123")

    def test_compound_word_accepted(self):
        assert not SiteAnalysisService._is_url_or_domain_token("on-page")
        assert not SiteAnalysisService._is_url_or_domain_token("real-estate")


# ════════════════════════════════════════════════════════════════════════════
# Integration: _extract_target_keywords on fake pages
# ════════════════════════════════════════════════════════════════════════════


class _FakePage:
    """Minimal mock of a crawled page for testing keyword extraction."""

    def __init__(self, html: str, *, is_html: bool = True) -> None:
        self._html = html
        self.is_html = is_html

    def decoded_text(self) -> str:
        return self._html


class TestExtractTargetKeywordsRegression:
    """Regression: garbled keywords must not appear in output."""

    def _make_service(self) -> SiteAnalysisService:
        """Return a minimal service instance with just enough wiring."""
        # We only call a static-ish method, but need an instance.
        # Patch the constructor to skip real services.
        from unittest.mock import MagicMock

        svc = object.__new__(SiteAnalysisService)
        svc._crawl_service = MagicMock()
        svc._audit_service = MagicMock()
        svc._content_service = MagicMock()
        svc._search_provider = MagicMock()
        svc._repository = MagicMock()
        svc._crux_service = None
        svc._collection_service = MagicMock()
        svc._intelligence_service = MagicMock()
        return svc

    def test_no_quot_from_html_entities(self):
        """&quot; in HTML must NOT produce 'quot' keyword."""
        svc = self._make_service()
        html = (
            "<html><head><title>Best Marketing Tools</title></head>"
            "<body>"
            "<p>&quot;SEO &amp; Marketing&quot; is the key to success.</p>"
            "<p>&quot;Digital Marketing&quot; includes many strategies.</p>"
            "<p>&quot;Content Marketing&quot; drives organic traffic.</p>"
            "<p>&quot;Email Marketing&quot; remains effective.</p>"
            "<p>&quot;Social Media Marketing&quot; builds brand awareness.</p>"
            "<p>&quot;Marketing Strategy&quot; is essential for growth.</p>"
            "<p>&quot;Marketing Automation&quot; saves time.</p>"
            "<p>&quot;Marketing Analytics&quot; measure performance.</p>"
            "</body></html>"
        ) * 5  # Repeat to exceed min text length
        pages = [_FakePage(html)]
        keywords = svc._extract_target_keywords(pages, max_keywords=50)
        for kw in keywords:
            assert kw.lower() != "quot", f"'quot' should not appear in keywords: {keywords}"
            assert "quot" not in kw.lower(), f"HTML entity artifact found in keyword: {kw}"

    def test_no_url_fragments(self):
        """URL-like tokens should not appear as keywords."""
        svc = self._make_service()
        html = (
            "<html><head><title>Marketing Tips</title></head>"
            "<body>"
            "<p>Visit https://dpskhanapara.com for more info</p>"
            "<p>Check http://example.com/path/to/page here</p>"
            "<p>Visit https://another-site.org/articles</p>"
            "<p>Good marketing advice at www.test.com</p>"
            "<p>More content about digital marketing strategies</p>"
            "<p>Email marketing is effective for business growth</p>"
            "</body></html>"
        ) * 5
        pages = [_FakePage(html)]
        keywords = svc._extract_target_keywords(pages, max_keywords=50)
        for kw in keywords:
            assert kw.lower() != "https", f"'https' should not appear: {keywords}"
            assert kw.lower() != "http", f"'http' should not appear: {keywords}"
            assert kw.lower() != "com", f"'com' should not appear: {keywords}"
            assert kw.lower() != "dpskhanapara", f"domain fragment should not appear: {keywords}"

    def test_legitimate_keywords_preserved(self):
        """Real content words should still be extracted."""
        svc = self._make_service()
        html = (
            "<html><head><title>Marketing Guide</title></head>"
            "<body>"
            "<h1>Digital Marketing Strategies</h1>"
            "<p>Search engine optimization is crucial for online marketing.</p>"
            "<p>Content marketing helps build authority and trust.</p>"
            "<p>Email marketing campaigns drive business growth.</p>"
            "<p>Social media marketing increases brand awareness.</p>"
            "<p>Marketing automation tools save time and resources.</p>"
            "</body></html>"
        ) * 5
        pages = [_FakePage(html)]
        keywords = svc._extract_target_keywords(pages, max_keywords=50)
        kw_lower = {kw.lower() for kw in keywords}
        # At least some real marketing terms should be present
        assert any("marketing" in kw for kw in kw_lower), (
            f"Expected 'marketing' in keywords: {keywords}"
        )

    def test_bigrams_not_polluted(self):
        """Bigrams should not contain URL/entity artifacts."""
        svc = self._make_service()
        html = (
            "<html><head><title>Business Tips</title></head>"
            "<body>"
            "<p>&quot;Digital Marketing&quot; is popular.</p>"
            "<p>&quot;Online Marketing&quot; works well.</p>"
            "<p>&quot;Business Marketing&quot; drives growth.</p>"
            "<p>&quot;Marketing Strategy&quot; matters.</p>"
            "<p>&quot;Business Strategy&quot; is important.</p>"
            "<p>Visit https://example.com for more.</p>"
            "<p>Good business advice and marketing tips.</p>"
            "</body></html>"
        ) * 5
        pages = [_FakePage(html)]
        keywords = svc._extract_target_keywords(pages, max_keywords=50)
        for kw in keywords:
            assert "quot" not in kw.lower(), f"Entity artifact in keyword: {kw}"
            assert not kw.lower().startswith("http"), f"URL fragment in keyword: {kw}"
