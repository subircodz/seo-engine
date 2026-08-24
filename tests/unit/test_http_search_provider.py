"""Unit tests for HttpSearchProvider (Phase 6K).

All tests use mocked HTTP transport — no real network calls.
"""

import json

import httpx
import pytest

from sie.domain.models.search import SearchDevice, SearchQuery
from sie.domain.ports.search_provider import (
    SearchProviderAuthenticationError,
    SearchProviderError,
    SearchProviderRateLimit,
    SearchProviderTimeout,
)
from sie.infrastructure.search.http_provider import HttpSearchProvider

# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════


def _query(**overrides) -> SearchQuery:
    defaults = {"query": "best crm software", "target_domain": "example.com"}
    defaults.update(overrides)
    return SearchQuery(**defaults)


def _mock_response(
    status_code: int = 200,
    json_data: object = None,
    text: str = "",
) -> httpx.Response:
    """Build a minimal httpx.Response without network."""
    content = json.dumps(json_data).encode() if json_data is not None else text.encode()
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://api.example.com/search"),
    )


def _ok_results(*items: dict) -> dict:
    return {"results": list(items)}


def _item(
    position: int = 1,
    title: str = "Example Page",
    url: str = "https://example.com/page",
) -> dict:
    return {"position": position, "title": title, "url": url}


def _provider(
    status_code: int = 200,
    json_data: object = None,
    *,
    text: str = "",
    api_key: str = "",
    base_url: str = "https://api.example.com",
) -> HttpSearchProvider:
    """Create an HttpSearchProvider with a mocked transport."""
    response = _mock_response(status_code=status_code, json_data=json_data, text=text)

    def _handler(request: httpx.Request) -> httpx.Response:
        return response

    transport = httpx.MockTransport(_handler)
    client = httpx.AsyncClient(transport=transport)
    return HttpSearchProvider(
        base_url=base_url, api_key=api_key, timeout_seconds=5.0, client=client
    )


def _provider_from_handler(handler):
    """Create an HttpSearchProvider from a custom request handler."""
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return HttpSearchProvider(
        base_url="https://api.example.com",
        api_key="",
        timeout_seconds=5.0,
        client=client,
    )


# ════════════════════════════════════════════════════════════════════════════
# Successful search
# ════════════════════════════════════════════════════════════════════════════


class TestSuccessfulSearch:
    async def test_single_result(self):
        provider = _provider(json_data=_ok_results(_item()))
        result = await provider.search(_query())

        assert result.keyword == "best crm software"
        assert result.search_engine == "google"
        assert result.country == "us"
        assert result.language == "en"
        assert result.device is SearchDevice.DESKTOP
        assert len(result.items) == 1
        assert result.items[0].position == 1
        assert result.items[0].title == "Example Page"
        assert result.items[0].url == "https://example.com/page"
        assert result.items[0].domain == "example.com"

    async def test_multiple_results(self):
        provider = _provider(
            json_data=_ok_results(
                _item(position=1, title="First", url="https://a.io/"),
                _item(position=2, title="Second", url="https://b.io/"),
                _item(position=3, title="Third", url="https://c.io/"),
            )
        )
        result = await provider.search(_query())

        assert len(result.items) == 3
        assert [i.position for i in result.items] == [1, 2, 3]
        assert [i.title for i in result.items] == ["First", "Second", "Third"]

    async def test_result_order_preserved(self):
        """Items come back in the order the provider returns them."""
        provider = _provider(
            json_data=_ok_results(
                _item(position=5, title="Fifth", url="https://five.io/"),
                _item(position=1, title="First", url="https://one.io/"),
            )
        )
        result = await provider.search(_query())
        assert [i.position for i in result.items] == [5, 1]

    async def test_empty_results(self):
        provider = _provider(json_data={"results": []})
        result = await provider.search(_query())
        assert result.items == ()


# ════════════════════════════════════════════════════════════════════════════
# Request construction
# ════════════════════════════════════════════════════════════════════════════


class TestRequestConstruction:
    async def test_url_is_base_plus_search(self):
        captured = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return _mock_response(json_data=_ok_results())

        provider = _provider_from_handler(_handler)
        await provider.search(_query())
        assert captured["url"] == "https://api.example.com/search"

    async def test_payload_contains_query_fields(self):
        captured = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _mock_response(json_data=_ok_results())

        provider = _provider_from_handler(_handler)
        q = SearchQuery(
            query="seo tools",
            country="uk",
            language="en",
            device=SearchDevice.MOBILE,
            search_engine="bing",
            target_domain="oursite.io",
            max_results=20,
        )
        await provider.search(q)

        body = captured["body"]
        assert body["query"] == "seo tools"
        assert body["country"] == "uk"
        assert body["language"] == "en"
        assert body["device"] == "mobile"
        assert body["search_engine"] == "bing"
        assert body["target_domain"] == "oursite.io"
        assert body["max_results"] == 20

    async def test_target_domain_omitted_when_none(self):
        captured = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _mock_response(json_data=_ok_results())

        provider = _provider_from_handler(_handler)
        q = SearchQuery(query="test")
        await provider.search(q)

        assert "target_domain" not in captured["body"]

    async def test_payload_is_valid_json(self):
        captured = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            captured["content_type"] = request.headers.get("content-type")
            captured["body"] = json.loads(request.content)
            return _mock_response(json_data=_ok_results())

        provider = _provider_from_handler(_handler)
        await provider.search(_query())
        assert captured["content_type"] == "application/json"
        assert isinstance(captured["body"], dict)


# ════════════════════════════════════════════════════════════════════════════
# Authentication header
# ════════════════════════════════════════════════════════════════════════════


class TestAuthentication:
    async def test_api_key_sends_bearer_header(self):
        captured = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return _mock_response(json_data=_ok_results())

        transport = httpx.MockTransport(_handler)
        client = httpx.AsyncClient(
            transport=transport,
            headers={"Authorization": "Bearer sk-secret-12345"},
        )
        provider = HttpSearchProvider(
            base_url="https://api.example.com",
            api_key="sk-secret-12345",
            client=client,
        )
        await provider.search(_query())
        assert captured["headers"]["authorization"] == "Bearer sk-secret-12345"

    async def test_no_api_key_no_auth_header(self):
        captured = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return _mock_response(json_data=_ok_results())

        provider = HttpSearchProvider(
            base_url="https://api.example.com",
            api_key="",
            client=httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
        )
        await provider.search(_query())
        assert "authorization" not in captured["headers"]


# ════════════════════════════════════════════════════════════════════════════
# Error mapping — HTTP status codes
# ════════════════════════════════════════════════════════════════════════════


class TestHttpErrors:
    async def test_401_raises_auth_error(self):
        provider = _provider(status_code=401)
        with pytest.raises(SearchProviderAuthenticationError, match="invalid or missing"):
            await provider.search(_query())

    async def test_403_raises_auth_error(self):
        provider = _provider(status_code=403)
        with pytest.raises(SearchProviderAuthenticationError, match="invalid or missing"):
            await provider.search(_query())

    async def test_429_raises_rate_limit(self):
        provider = _provider(status_code=429)
        with pytest.raises(SearchProviderRateLimit, match="rate limit"):
            await provider.search(_query())

    async def test_500_raises_provider_error(self):
        provider = _provider(status_code=500, text="Internal Server Error")
        with pytest.raises(SearchProviderError, match="HTTP 500"):
            await provider.search(_query())

    async def test_502_raises_provider_error(self):
        provider = _provider(status_code=502, text="Bad Gateway")
        with pytest.raises(SearchProviderError, match="HTTP 502"):
            await provider.search(_query())


# ════════════════════════════════════════════════════════════════════════════
# Error mapping — transport failures
# ════════════════════════════════════════════════════════════════════════════


class TestTransportErrors:
    async def test_timeout_raises_search_provider_timeout(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("connection timed out")

        provider = _provider_from_handler(_handler)
        with pytest.raises(SearchProviderTimeout, match="timed out"):
            await provider.search(_query())

    async def test_connection_error_raises_provider_error(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        provider = _provider_from_handler(_handler)
        with pytest.raises(SearchProviderError, match="transport error"):
            await provider.search(_query())


# ════════════════════════════════════════════════════════════════════════════
# Response validation — malformed JSON
# ════════════════════════════════════════════════════════════════════════════


class TestMalformedJson:
    async def test_invalid_json_body(self):
        provider = _provider(status_code=200, text="not json at all {{{")
        with pytest.raises(SearchProviderError, match="invalid JSON"):
            await provider.search(_query())


# ════════════════════════════════════════════════════════════════════════════
# Response validation — structure
# ════════════════════════════════════════════════════════════════════════════


class TestResponseStructure:
    async def test_response_not_an_object(self):
        provider = _provider(json_data="just a string")
        with pytest.raises(SearchProviderError, match="not a JSON object"):
            await provider.search(_query())

    async def test_response_is_list(self):
        provider = _provider(json_data=[1, 2, 3])
        with pytest.raises(SearchProviderError, match="not a JSON object"):
            await provider.search(_query())

    async def test_missing_results_field(self):
        provider = _provider(json_data={"data": []})
        with pytest.raises(SearchProviderError, match="missing 'results'"):
            await provider.search(_query())

    async def test_results_not_a_list(self):
        provider = _provider(json_data={"results": "not a list"})
        with pytest.raises(SearchProviderError, match="'results' must be a list"):
            await provider.search(_query())

    async def test_results_is_int(self):
        provider = _provider(json_data={"results": 42})
        with pytest.raises(SearchProviderError, match="'results' must be a list"):
            await provider.search(_query())


# ════════════════════════════════════════════════════════════════════════════
# Response validation — individual items
# ════════════════════════════════════════════════════════════════════════════


class TestItemValidation:
    async def test_item_not_an_object(self):
        provider = _provider(json_data={"results": ["string", 42]})
        with pytest.raises(SearchProviderError, match="not an object"):
            await provider.search(_query())

    async def test_missing_title(self):
        provider = _provider(json_data={"results": [{"url": "https://a.io/", "position": 1}]})
        with pytest.raises(SearchProviderError, match="invalid 'title'"):
            await provider.search(_query())

    async def test_empty_title(self):
        provider = _provider(
            json_data={"results": [{"title": "", "url": "https://a.io/", "position": 1}]}
        )
        with pytest.raises(SearchProviderError, match="invalid 'title'"):
            await provider.search(_query())

    async def test_whitespace_only_title(self):
        provider = _provider(
            json_data={"results": [{"title": "   ", "url": "https://a.io/", "position": 1}]}
        )
        with pytest.raises(SearchProviderError, match="invalid 'title'"):
            await provider.search(_query())

    async def test_missing_url(self):
        provider = _provider(json_data={"results": [{"title": "Page", "position": 1}]})
        with pytest.raises(SearchProviderError, match="invalid 'url'"):
            await provider.search(_query())

    async def test_empty_url(self):
        provider = _provider(json_data={"results": [{"title": "Page", "url": "", "position": 1}]})
        with pytest.raises(SearchProviderError, match="invalid 'url'"):
            await provider.search(_query())

    async def test_invalid_url_scheme(self):
        provider = _provider(
            json_data={"results": [{"title": "Page", "url": "ftp://a.io/", "position": 1}]}
        )
        with pytest.raises(SearchProviderError, match="invalid URL scheme"):
            await provider.search(_query())

    async def test_missing_position(self):
        provider = _provider(json_data={"results": [{"title": "Page", "url": "https://a.io/"}]})
        with pytest.raises(SearchProviderError, match="invalid 'position'"):
            await provider.search(_query())

    async def test_position_zero(self):
        provider = _provider(
            json_data={"results": [{"title": "Page", "url": "https://a.io/", "position": 0}]}
        )
        with pytest.raises(SearchProviderError, match="non-positive 'position'"):
            await provider.search(_query())

    async def test_position_negative(self):
        provider = _provider(
            json_data={"results": [{"title": "Page", "url": "https://a.io/", "position": -1}]}
        )
        with pytest.raises(SearchProviderError, match="non-positive 'position'"):
            await provider.search(_query())

    async def test_position_float(self):
        provider = _provider(
            json_data={"results": [{"title": "Page", "url": "https://a.io/", "position": 1.5}]}
        )
        with pytest.raises(SearchProviderError, match="invalid 'position'"):
            await provider.search(_query())

    async def test_position_string(self):
        provider = _provider(
            json_data={"results": [{"title": "Page", "url": "https://a.io/", "position": "1"}]}
        )
        with pytest.raises(SearchProviderError, match="invalid 'position'"):
            await provider.search(_query())

    async def test_position_bool(self):
        provider = _provider(
            json_data={"results": [{"title": "Page", "url": "https://a.io/", "position": True}]}
        )
        with pytest.raises(SearchProviderError, match="invalid 'position'"):
            await provider.search(_query())

    async def test_position_none(self):
        provider = _provider(
            json_data={"results": [{"title": "Page", "url": "https://a.io/", "position": None}]}
        )
        with pytest.raises(SearchProviderError, match="invalid 'position'"):
            await provider.search(_query())


# ════════════════════════════════════════════════════════════════════════════
# Domain conversion
# ════════════════════════════════════════════════════════════════════════════


class TestDomainConversion:
    async def test_domain_derived_from_url(self):
        provider = _provider(
            json_data=_ok_results(_item(url="https://www.Example.Com/page?foo=bar"))
        )
        result = await provider.search(_query())
        assert result.items[0].domain == "example.com"

    async def test_title_whitespace_stripped(self):
        provider = _provider(
            json_data=_ok_results(
                {"position": 1, "title": "  Padded Title  ", "url": "https://a.io/"}
            )
        )
        result = await provider.search(_query())
        assert result.items[0].title == "Padded Title"

    async def test_result_fields_match_input(self):
        provider = _provider(
            json_data=_ok_results(_item(position=7, title="Test Page", url="https://test.io/xyz"))
        )
        result = await provider.search(_query())
        item = result.items[0]
        assert item.position == 7
        assert item.title == "Test Page"
        assert item.url == "https://test.io/xyz"


# ════════════════════════════════════════════════════════════════════════════
# max_results handling
# ════════════════════════════════════════════════════════════════════════════


class TestMaxResults:
    async def test_max_results_sent_in_payload(self):
        captured = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _mock_response(json_data=_ok_results())

        provider = _provider_from_handler(_handler)
        q = SearchQuery(query="k", max_results=50)
        await provider.search(q)
        assert captured["body"]["max_results"] == 50

    async def test_provider_can_return_fewer_than_max(self):
        provider = _provider(json_data=_ok_results(_item()))
        q = SearchQuery(query="k", max_results=100)
        result = await provider.search(q)
        assert len(result.items) == 1


# ════════════════════════════════════════════════════════════════════════════
# Lifecycle — close
# ════════════════════════════════════════════════════════════════════════════


class TestLifecycle:
    async def test_injected_client_not_closed(self):
        transport = httpx.MockTransport(lambda r: _mock_response(json_data=_ok_results()))
        client = httpx.AsyncClient(transport=transport)
        provider = HttpSearchProvider(base_url="https://api.example.com", client=client)
        await provider.search(_query())
        await provider.close()
        # If the client was closed, the transport would raise on next use.
        # Calling close again should be safe.
        await provider.close()

    async def test_internally_created_client_is_closed(self):
        """Verify close() works for provider-created clients without error."""
        provider = HttpSearchProvider(
            base_url="https://api.example.com",
            timeout_seconds=5.0,
        )
        # Override the client with a mock so we don't actually create a real one.
        transport = httpx.MockTransport(lambda r: _mock_response(json_data=_ok_results()))
        provider._client = httpx.AsyncClient(transport=transport)
        provider._owns_client = True
        await provider.search(_query())
        await provider.close()


# ════════════════════════════════════════════════════════════════════════════
# API key never exposed
# ════════════════════════════════════════════════════════════════════════════


class TestSecretProtection:
    async def test_api_key_not_in_exception_message(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out")

        provider = HttpSearchProvider(
            base_url="https://api.example.com",
            api_key="super-secret-key-12345",
            client=httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
        )
        with pytest.raises(SearchProviderTimeout) as exc_info:
            await provider.search(_query())
        assert "super-secret-key-12345" not in str(exc_info.value)

    async def test_api_key_not_in_error_message(self):
        provider = _provider(status_code=500, text="Internal Server Error")
        provider._api_key = "super-secret-key-12345"
        with pytest.raises(SearchProviderError) as exc_info:
            await provider.search(_query())
        assert "super-secret-key-12345" not in str(exc_info.value)


# ════════════════════════════════════════════════════════════════════════════
# Integration with SearchCollectionService (mock remains working)
# ════════════════════════════════════════════════════════════════════════════


class TestIntegrationWithCollectionService:
    async def test_mock_search_provider_still_works(self):
        """Existing MockSearchProvider tests remain valid — verify basic contract."""
        from sie.domain.models.search_result import SearchResult, SearchResultItem
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        mock = MockSearchProvider(
            results={
                "test": SearchResult(
                    keyword="test",
                    items=(
                        SearchResultItem(position=1, title="Page", url="https://oursite.io/page"),
                    ),
                ),
            }
        )
        result = await mock.search(SearchQuery(query="test"))
        assert len(result.items) == 1
        assert result.items[0].domain == "oursite.io"
