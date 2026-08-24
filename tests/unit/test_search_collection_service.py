"""Unit tests for Search Collection Service (Phase 6H)."""

from datetime import UTC, datetime

import pytest

from sie.domain.models.search import SearchDevice, SearchQuery
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.ports.search_provider import (
    SearchProviderAuthenticationError,
    SearchProviderError,
    SearchProviderRateLimit,
    SearchProviderTimeout,
)
from sie.domain.services.search_collection_service import SearchCollectionService
from sie.infrastructure.search.mock_provider import MockSearchProvider

# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════


def _item(pos: int, url: str = "https://oursite.io/page", title: str = "Title") -> SearchResultItem:
    return SearchResultItem(position=pos, title=title, url=url)


def _result(
    keyword: str = "seo tools",
    items: tuple[SearchResultItem, ...] = (),
    **kwargs,
) -> SearchResult:
    return SearchResult(keyword=keyword, items=items, **kwargs)


def _query(
    keyword: str = "seo tools",
    target_domain: str | None = "oursite.io",
    **kwargs,
) -> SearchQuery:
    return SearchQuery(query=keyword, target_domain=target_domain, **kwargs)


# ════════════════════════════════════════════════════════════════════════════
# Target domain found
# ════════════════════════════════════════════════════════════════════════════


class TestTargetFound:
    async def test_target_at_position_1(self):
        provider = MockSearchProvider(
            results={"seo tools": _result(items=(_item(1), _item(2, url="https://other.io/")))}
        )
        svc = SearchCollectionService(provider, source="test")
        items = await svc.collect([_query()])
        assert len(items) == 1
        assert items[0].found is True
        assert items[0].observation is not None
        assert items[0].observation.position == 1
        assert items[0].observation.target_url == "https://oursite.io/page"

    async def test_target_at_position_10(self):
        items_tuple = (
            *tuple(_item(i, url=f"https://r{i}.io/") for i in range(1, 10)),
            _item(10, url="https://oursite.io/p"),
        )
        provider = MockSearchProvider(results={"kw": _result(keyword="kw", items=items_tuple)})
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="kw")])
        assert results[0].found is True
        assert results[0].observation is not None
        assert results[0].observation.position == 10

    async def test_first_matching_item_used(self):
        """If target appears multiple times, the first occurrence is used."""
        provider = MockSearchProvider(
            results={
                "kw": _result(
                    keyword="kw",
                    items=(
                        _item(3, url="https://other.io/"),
                        _item(7, url="https://oursite.io/x"),
                        _item(9, url="https://oursite.io/y"),
                    ),
                )
            }
        )
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="kw")])
        assert results[0].observation is not None
        assert results[0].observation.position == 7


# ════════════════════════════════════════════════════════════════════════════
# Target domain not found
# ════════════════════════════════════════════════════════════════════════════


class TestTargetNotFound:
    async def test_not_found_returns_none_observation(self):
        provider = MockSearchProvider(
            results={"kw": _result(keyword="kw", items=(_item(1, url="https://other.io/"),))}
        )
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="kw")])
        assert results[0].found is False
        assert results[0].observation is None

    async def test_empty_results_not_found(self):
        provider = MockSearchProvider(results={"kw": _result(keyword="kw", items=())})
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="kw")])
        assert results[0].found is False
        assert results[0].observation is None

    async def test_no_target_domain_not_found(self):
        """When target_domain is None, observation is None."""
        provider = MockSearchProvider(results={"kw": _result(keyword="kw", items=(_item(1),))})
        query = SearchQuery(query="kw")
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([query])
        assert results[0].found is False
        assert results[0].observation is None


# ════════════════════════════════════════════════════════════════════════════
# Multiple queries
# ════════════════════════════════════════════════════════════════════════════


class TestMultipleQueries:
    async def test_multiple_queries_preserves_order(self):
        provider = MockSearchProvider(
            results={
                "a": _result(keyword="a", items=(_item(1, url="https://oursite.io/a"),)),
                "b": _result(keyword="b", items=(_item(5, url="https://other.io/b"),)),
                "c": _result(keyword="c", items=(_item(3, url="https://oursite.io/c"),)),
            }
        )
        svc = SearchCollectionService(provider, source="test")
        queries = [_query(keyword="c"), _query(keyword="a"), _query(keyword="b")]
        results = await svc.collect(queries)
        assert len(results) == 3
        # Order matches input.
        assert [r.query.query for r in results] == ["c", "a", "b"]
        # c=3 found, a=1 found, b=5 not found (different domain)
        assert results[0].found is True
        assert results[0].observation is not None
        assert results[0].observation.position == 3
        assert results[1].found is True
        assert results[1].observation is not None
        assert results[1].observation.position == 1
        assert results[2].found is False

    async def test_single_query(self):
        provider = MockSearchProvider(
            results={"kw": _result(keyword="kw", items=(_item(2, url="https://oursite.io/"),))}
        )
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="kw")])
        assert len(results) == 1
        assert results[0].found is True


# ════════════════════════════════════════════════════════════════════════════
# Metadata propagation
# ════════════════════════════════════════════════════════════════════════════


class TestMetadataPropagation:
    async def test_metadata_preserved_on_observation(self):
        query = _query(
            keyword="seo tools",
            search_engine="bing",
            country="uk",
            language="en",
            target_domain="oursite.io",
        )
        provider = MockSearchProvider(
            results={
                "seo tools": _result(
                    keyword="seo tools",
                    search_engine="bing",
                    country="uk",
                    language="en",
                    items=(_item(1, url="https://oursite.io/tools"),),
                )
            }
        )
        svc = SearchCollectionService(provider, source="serpapi-test")
        results = await svc.collect([query])
        obs = results[0].observation
        assert obs is not None
        assert obs.keyword == "seo tools"
        assert obs.search_engine == "bing"
        assert obs.country == "uk"
        assert obs.language == "en"
        assert obs.source == "serpapi-test"
        assert obs.device is SearchDevice.DESKTOP

    async def test_device_propagated(self):
        query = _query(keyword="k", target_domain="oursite.io", device=SearchDevice.MOBILE)
        provider = MockSearchProvider(
            results={"k": _result(keyword="k", items=(_item(1, url="https://oursite.io/"),))}
        )
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([query])
        assert results[0].observation is not None
        assert results[0].observation.device is SearchDevice.MOBILE

    async def test_observed_at_is_set(self):
        provider = MockSearchProvider(
            results={"k": _result(keyword="k", items=(_item(1, url="https://oursite.io/"),))}
        )
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="k")])
        obs = results[0].observation
        assert obs is not None
        assert isinstance(obs.observed_at, datetime)
        assert obs.observed_at.tzinfo is UTC


# ════════════════════════════════════════════════════════════════════════════
# Mock provider behaviour
# ════════════════════════════════════════════════════════════════════════════


class TestMockProvider:
    async def test_returns_configured_result(self):
        result = _result(keyword="k", items=(_item(1),))
        provider = MockSearchProvider(results={"k": result})
        query = SearchQuery(query="k")
        returned = await provider.search(query)
        assert returned is result

    async def test_missing_result_raises_key_error(self):
        provider = MockSearchProvider(results={})
        with pytest.raises(KeyError, match="no result configured"):
            await provider.search(SearchQuery(query="missing"))

    async def test_records_calls(self):
        provider = MockSearchProvider(results={"k": _result(keyword="k")})
        q1 = SearchQuery(query="k")
        q2 = SearchQuery(query="k", country="uk")
        await provider.search(q1)
        await provider.search(q2)
        assert len(provider.calls) == 2
        assert provider.calls[0].country == "us"
        assert provider.calls[1].country == "uk"

    async def test_no_network_calls(self):
        """Verify the mock provider does not make real network calls."""
        provider = MockSearchProvider(results={"k": _result(keyword="k")})
        query = SearchQuery(query="k")
        # If any network call were made, it would fail in a hermetic test env.
        result = await provider.search(query)
        assert isinstance(result, SearchResult)


# ════════════════════════════════════════════════════════════════════════════
# Provider error propagation
# ════════════════════════════════════════════════════════════════════════════


class TestProviderErrors:
    async def test_error_propagates(self):
        class BrokenProvider:
            async def search(self, query):
                raise SearchProviderError("something broke")

        svc = SearchCollectionService(BrokenProvider(), source="test")
        with pytest.raises(SearchProviderError, match="something broke"):
            await svc.collect([_query()])

    async def test_timeout_propagates(self):
        class TimeoutProvider:
            async def search(self, query):
                raise SearchProviderTimeout("timed out")

        svc = SearchCollectionService(TimeoutProvider(), source="test")
        with pytest.raises(SearchProviderTimeout, match="timed out"):
            await svc.collect([_query()])

    async def test_rate_limit_propagates(self):
        class RateLimitProvider:
            async def search(self, query):
                raise SearchProviderRateLimit("slow down")

        svc = SearchCollectionService(RateLimitProvider(), source="test")
        with pytest.raises(SearchProviderRateLimit, match="slow down"):
            await svc.collect([_query()])

    async def test_auth_error_propagates(self):
        class AuthProvider:
            async def search(self, query):
                raise SearchProviderAuthenticationError("bad key")

        svc = SearchCollectionService(AuthProvider(), source="test")
        with pytest.raises(SearchProviderAuthenticationError, match="bad key"):
            await svc.collect([_query()])


# ════════════════════════════════════════════════════════════════════════════
# Deterministic ordering
# ════════════════════════════════════════════════════════════════════════════


class TestDeterminism:
    async def test_same_input_same_output(self):
        provider = MockSearchProvider(
            results={
                "kw": _result(
                    keyword="kw",
                    items=(
                        _item(3, url="https://a.io/"),
                        _item(1, url="https://oursite.io/"),
                        _item(7, url="https://b.io/"),
                    ),
                )
            }
        )
        svc = SearchCollectionService(provider, source="test")
        r1 = await svc.collect([_query(keyword="kw")])
        r2 = await svc.collect([_query(keyword="kw")])
        assert r1[0].observation is not None
        assert r2[0].observation is not None
        assert r1[0].observation.position == r2[0].observation.position
        assert r1[0].found == r2[0].found


# ════════════════════════════════════════════════════════════════════════════
# Domain matching edge cases
# ════════════════════════════════════════════════════════════════════════════


class TestDomainMatching:
    async def test_domain_with_www_in_result(self):
        """Result domain has www. prefix — should still match target."""
        provider = MockSearchProvider(
            results={
                "k": _result(keyword="k", items=(_item(1, url="https://www.oursite.io/page"),))
            }
        )
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="k")])
        assert results[0].found is True

    async def test_domain_case_insensitive(self):
        provider = MockSearchProvider(
            results={"k": _result(keyword="k", items=(_item(1, url="https://OurSite.IO/page"),))}
        )
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="k", target_domain="OurSite.IO")])
        assert results[0].found is True

    async def test_domain_with_www_in_query(self):
        """Query target_domain has www. prefix — normalized away at construction."""
        provider = MockSearchProvider(
            results={"k": _result(keyword="k", items=(_item(1, url="https://oursite.io/"),))}
        )
        svc = SearchCollectionService(provider, source="test")
        results = await svc.collect([_query(keyword="k", target_domain="www.oursite.io")])
        assert results[0].found is True
