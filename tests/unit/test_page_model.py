"""FetchedPage value-object behaviour."""

import dataclasses

import pytest

from sie.domain.models.page import FetchedPage


def _page(**overrides) -> FetchedPage:
    defaults: dict = {
        "url": "https://example.com/",
        "final_url": "https://example.com/",
        "status_code": 200,
        "headers": {},
        "content": b"<html></html>",
        "content_type": "text/html; charset=utf-8",
    }
    defaults.update(overrides)
    return FetchedPage(**defaults)


def test_ok_and_is_html() -> None:
    page = _page()
    assert page.ok is True
    assert page.is_html is True


def test_error_status_is_data_not_exception() -> None:
    page = _page(status_code=404)
    assert page.ok is False
    assert page.status_code == 404


def test_decoded_text_honours_declared_charset() -> None:
    page = _page(content="café".encode("cp1252"), encoding="cp1252")
    assert page.decoded_text() == "café"


def test_decoded_text_falls_back_to_utf8() -> None:
    page = _page(content="café".encode(), encoding=None)
    assert page.decoded_text() == "café"


def test_page_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _page().status_code = 500  # type: ignore[misc]
