"""Technical SEO title rule tests."""

from sie.domain.engines.technical_seo import (
    TitleDuplicateRule,
    TitleEmptyRule,
    TitleMissingRule,
    TitleTooLongRule,
)
from sie.domain.models.audit import AuditContext, PageDOM

RULE = TitleMissingRule()


def _dom(title=None, url="https://example.com/"):
    return PageDOM(url=url, status_code=200, title=title, content_type="text/html")


def test_missing_title_detected():
    finding = RULE.check(_dom(title=None))
    assert finding is not None
    assert finding.rule_code == "TITLE_MISSING"
    assert finding.severity == "critical"


def test_present_title_ok():
    assert RULE.check(_dom(title="Hello")) is None


def test_empty_title_detected():
    finding = TitleEmptyRule().check(_dom(title="   "))
    assert finding is not None
    assert finding.rule_code == "TITLE_EMPTY"


def test_long_title_detected():
    finding = TitleTooLongRule().check(_dom(title="A" * 61))
    assert finding is not None
    assert "61 chars" in finding.message


def test_short_title_ok():
    assert TitleTooLongRule().check(_dom(title="Short")) is None


def test_duplicate_title_detected():
    ctx = AuditContext(
        pages_by_url={
            "https://example.com/a": PageDOM(
                url="https://example.com/a", status_code=200, title="Same", content_type="text/html"
            ),
            "https://example.com/b": PageDOM(
                url="https://example.com/b", status_code=200, title="Same", content_type="text/html"
            ),
        }
    )
    finding = TitleDuplicateRule().check(_dom(title="Same", url="https://example.com/a"), ctx)
    assert finding is not None
    assert "Duplicate title" in finding.message
    assert "https://example.com/b" in finding.affected_elements


def test_unique_title_not_duplicate():
    ctx = AuditContext(
        pages_by_url={
            "https://example.com/a": PageDOM(
                url="https://example.com/a",
                status_code=200,
                title="Alpha",
                content_type="text/html",
            ),
            "https://example.com/b": PageDOM(
                url="https://example.com/b", status_code=200, title="Beta", content_type="text/html"
            ),
        }
    )
    assert TitleDuplicateRule().check(_dom(title="Alpha", url="https://example.com/a"), ctx) is None
