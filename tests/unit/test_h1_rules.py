"""Technical SEO H1 + status code + P1/P2 rule tests."""

from sie.domain.engines.technical_seo import (
    H1EmptyRule,
    H1MissingRule,
    H1MultipleRule,
    HeadingHierarchySkipRule,
    ImageAltMissingRule,
    InternalLinksTooFewRule,
    InternalLinksTooManyRule,
    JsonLdMissingRule,
    LargeHtmlRule,
    MetaRobotsNoindexRule,
    MixedContentRule,
    SslRedirectRule,
    Status5xxRule,
    Status404Rule,
    UrlExcessiveParamsRule,
    UrlSessionIdRule,
    run_technical_audit,
)
from sie.domain.models.audit import PageDOM, PageImage


def _dom(**kw):
    defaults = dict(url="https://example.com/", status_code=200, content_type="text/html")
    defaults.update(kw)
    return PageDOM(**defaults)


# ── H1 rules ────────────────────────────────────────────────────────────────


def test_h1_missing():
    assert H1MissingRule().check(_dom()) is not None


def test_h1_present_ok():
    assert H1MissingRule().check(_dom(h1s=("Title",))) is None


def test_h1_empty():
    finding = H1EmptyRule().check(_dom(h1s=("", "   ")))
    assert finding is not None


def test_h1_multiple():
    finding = H1MultipleRule().check(_dom(h1s=("A", "B")))
    assert finding is not None


# ── Status rules ────────────────────────────────────────────────────────────


def test_status_404():
    assert Status404Rule().check(_dom(status_code=404)) is not None


def test_status_5xx():
    finding = Status5xxRule().check(_dom(status_code=500))
    assert finding is not None


def test_status_200_ok():
    assert Status404Rule().check(_dom()) is None
    assert Status5xxRule().check(_dom()) is None


# ── P1 rules ────────────────────────────────────────────────────────────────


def test_noindex_detected():
    assert MetaRobotsNoindexRule().check(_dom(meta_robots="noindex")) is not None


def test_noindex_not_present_ok():
    assert MetaRobotsNoindexRule().check(_dom()) is None


def test_ssl_redirect():
    assert SslRedirectRule().check(_dom(url="http://example.com/")) is not None


def test_mixed_content():
    assert (
        MixedContentRule().check(_dom(url="https://example.com/", mixed_content=True)) is not None
    )


def test_large_html():
    finding = LargeHtmlRule().check(_dom(html_size=3 * 1024 * 1024))
    assert finding is not None
    assert "3.0 MB" in finding.message


def test_jsonld_missing():
    assert JsonLdMissingRule().check(_dom()) is not None


def test_jsonld_present_ok():
    assert JsonLdMissingRule().check(_dom(jsonld_types=("Article",))) is None


# ── P2 rules ────────────────────────────────────────────────────────────────


def test_heading_hierarchy_skip():
    finding = HeadingHierarchySkipRule().check(_dom(h1s=("H",), h3s=("Deep",)))
    assert finding is not None


def test_image_alt_missing():
    finding = ImageAltMissingRule().check(
        _dom(images=(PageImage(src="/a.png", alt=""), PageImage(src="/b.jpg", alt="photo")))
    )
    assert finding is not None
    assert "1 image" in finding.message


def test_image_all_alts_ok():
    assert ImageAltMissingRule().check(_dom(images=(PageImage(src="/a.png", alt="ok"),))) is None


def test_internal_links_too_few():
    assert InternalLinksTooFewRule().check(_dom(internal_links=("/a",))) is not None


def test_internal_links_too_many():
    assert (
        InternalLinksTooManyRule().check(_dom(internal_links=tuple(f"/p{i}" for i in range(101))))
        is not None
    )


def test_url_excessive_params():
    finding = UrlExcessiveParamsRule().check(_dom(url="https://example.com/?a=1&b=2&c=3&d=4"))
    assert finding is not None


def test_url_session_id():
    assert UrlSessionIdRule().check(_dom(url="https://example.com/page?PHPSESSID=abc")) is not None


# ── Engine-level aggregation ────────────────────────────────────────────────


def test_run_technical_audit_aggregation():
    pages = [_dom(h1s=(), meta_description=None, title=None), _dom(title="OK")]
    result = run_technical_audit(pages, priorities={"P0"})
    assert result.total_pages == 2
    assert result.total_issues > 0
    assert result.critical_count > 0
