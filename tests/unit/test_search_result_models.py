"""Unit tests for Search Result models (Phase 6H)."""

from dataclasses import FrozenInstanceError

import pytest

from sie.domain.models.search import SearchDevice
from sie.domain.models.search_result import SearchResult, SearchResultItem

# ════════════════════════════════════════════════════════════════════════════
# SearchResultItem
# ════════════════════════════════════════════════════════════════════════════


class TestSearchResultItem:
    def test_valid_item(self):
        item = SearchResultItem(position=1, title="Best CRM", url="https://oursite.io/crm")
        assert item.position == 1
        assert item.title == "Best CRM"
        assert item.url == "https://oursite.io/crm"
        assert item.domain == "oursite.io"

    def test_domain_strips_www(self):
        item = SearchResultItem(position=3, title="Page", url="https://www.example.com/path")
        assert item.domain == "example.com"

    def test_domain_is_casefolded(self):
        item = SearchResultItem(position=2, title="X", url="https://Example.Com/page")
        assert item.domain == "example.com"

    def test_domain_port_stripped(self):
        item = SearchResultItem(position=1, title="X", url="https://example.com:8080/page")
        assert item.domain == "example.com"

    def test_https_accepted(self):
        item = SearchResultItem(position=1, title="X", url="https://a.io/")
        assert item.url == "https://a.io/"

    def test_http_accepted(self):
        item = SearchResultItem(position=1, title="X", url="http://a.io/")
        assert item.url == "http://a.io/"

    @pytest.mark.parametrize("bad_position", [0, -1, -5])
    def test_non_positive_position_rejected(self, bad_position):
        with pytest.raises(ValueError, match="position"):
            SearchResultItem(position=bad_position, title="X", url="https://a.io/")

    @pytest.mark.parametrize("bad_position", [1.5, "3", True, None])
    def test_non_integer_position_rejected(self, bad_position):
        with pytest.raises(ValueError, match="position"):
            SearchResultItem(position=bad_position, title="X", url="https://a.io/")  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_url", ["example.com/page", "ftp://a.io/", "", "   "])
    def test_invalid_url_rejected(self, bad_url):
        with pytest.raises(ValueError, match="url"):
            SearchResultItem(position=1, title="X", url=bad_url)

    @pytest.mark.parametrize("bad_title", ["", "   ", None])
    def test_missing_title_rejected(self, bad_title):
        with pytest.raises(ValueError, match="title"):
            SearchResultItem(position=1, title=bad_title, url="https://a.io/")  # type: ignore[arg-type]

    def test_frozen(self):
        item = SearchResultItem(position=1, title="X", url="https://a.io/")
        with pytest.raises(FrozenInstanceError):
            item.position = 2  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════════
# SearchResult
# ════════════════════════════════════════════════════════════════════════════


class TestSearchResult:
    def test_valid_result_defaults(self):
        result = SearchResult(keyword="seo tools")
        assert result.keyword == "seo tools"
        assert result.search_engine == "google"
        assert result.country == "us"
        assert result.language == "en"
        assert result.device is SearchDevice.DESKTOP
        assert result.items == ()

    def test_result_with_items(self):
        items = (
            SearchResultItem(position=1, title="A", url="https://a.io/"),
            SearchResultItem(position=2, title="B", url="https://b.io/"),
        )
        result = SearchResult(keyword="tools", items=items)
        assert len(result.items) == 2
        assert result.items[0].position == 1
        assert result.items[1].position == 2

    def test_items_must_be_tuple(self):
        with pytest.raises(ValueError, match="items must be a tuple"):
            SearchResult(
                keyword="k", items=[SearchResultItem(position=1, title="X", url="https://a.io/")]
            )  # type: ignore[arg-type]

    def test_empty_items_allowed(self):
        result = SearchResult(keyword="k")
        assert result.items == ()

    def test_normalizes_context_fields(self):
        result = SearchResult(keyword="k", search_engine="Bing", country="US", language="EN")
        assert result.search_engine == "bing"
        assert result.country == "us"
        assert result.language == "en"

    def test_invalid_keyword_rejected(self):
        with pytest.raises(ValueError, match="keyword"):
            SearchResult(keyword="")

    def test_frozen(self):
        result = SearchResult(keyword="k")
        with pytest.raises(FrozenInstanceError):
            result.keyword = "changed"  # type: ignore[misc]

    def test_deterministic_item_ordering(self):
        """Items tuple preserves the order supplied by the provider."""
        items = (
            SearchResultItem(position=5, title="Fifth", url="https://five.io/"),
            SearchResultItem(position=1, title="First", url="https://one.io/"),
        )
        result = SearchResult(keyword="k", items=items)
        # Items are in the order given — provider controls ordering.
        assert [item.position for item in result.items] == [5, 1]
