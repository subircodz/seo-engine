"""Technical SEO meta rule tests."""

from sie.domain.engines.technical_seo import (
    CanonicalMissingRule,
    CanonicalMultipleRule,
    CanonicalSelfRefErrorRule,
    MetaDescDuplicateRule,
    MetaDescMissingRule,
    MetaDescTooLongRule,
)
from sie.domain.models.audit import AuditContext, PageDOM


def _dom(meta_desc=None, canonical=None, canonicals=None, url="https://example.com/"):
    return PageDOM(
        url=url,
        status_code=200,
        meta_description=meta_desc,
        canonical=canonical,
        canonicals=canonicals or (),
        content_type="text/html",
    )


def test_meta_desc_missing():
    assert MetaDescMissingRule().check(_dom()) is not None


def test_meta_desc_too_long():
    finding = MetaDescTooLongRule().check(_dom(meta_desc="A" * 161))
    assert finding is not None
    assert "161 chars" in finding.message


def test_meta_desc_duplicate():
    ctx = AuditContext(
        pages_by_url={
            "https://example.com/a": _dom(meta_desc="Same", url="https://example.com/a"),
            "https://example.com/b": _dom(meta_desc="Same", url="https://example.com/b"),
        }
    )
    finding = MetaDescDuplicateRule().check(
        _dom(meta_desc="Same", url="https://example.com/a"), ctx
    )
    assert finding is not None
    assert "Duplicate meta description" in finding.message


def test_canonical_missing():
    assert CanonicalMissingRule().check(_dom()) is not None


def test_canonical_self_ref_error():
    finding = CanonicalSelfRefErrorRule().check(
        _dom(canonical="https://example.com/other", url="https://example.com/page")
    )
    assert finding is not None
    assert "does not match page URL" in finding.message


def test_canonical_self_ref_ok():
    assert (
        CanonicalSelfRefErrorRule().check(
            _dom(canonical="https://example.com/page", url="https://example.com/page")
        )
        is None
    )


def test_canonical_multiple():
    finding = CanonicalMultipleRule().check(
        _dom(canonical="https://example.com/page", canonicals=("a", "b"))
    )
    assert finding is not None
    assert "Multiple canonical" in finding.message


def test_canonical_single_ok():
    assert CanonicalMultipleRule().check(_dom(canonicals=("a",))) is None
