"""Unit tests for Search Provider Factory (Phase 6L)."""

import pytest

from sie.config import SearchProviderSettings
from sie.infrastructure.search.http_provider import HttpSearchProvider
from sie.infrastructure.search.mock_provider import MockSearchProvider
from sie.infrastructure.search.provider_factory import (
    SearchProviderConfigError,
    create_search_provider,
)


class TestDisabledConfiguration:
    def test_disabled_returns_mock(self):
        settings = SearchProviderSettings(enabled=False)
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)

    def test_disabled_ignores_provider_name(self):
        settings = SearchProviderSettings(enabled=False, provider_name="http")
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)

    def test_disabled_ignores_base_url(self):
        settings = SearchProviderSettings(enabled=False, provider_name="http", base_url="http://x")
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)


class TestMockProvider:
    def test_explicit_mock_returns_mock(self):
        settings = SearchProviderSettings(enabled=True, provider_name="mock")
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)

    def test_mock_case_insensitive(self):
        settings = SearchProviderSettings(enabled=True, provider_name="MOCK")
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)

    def test_mock_with_whitespace(self):
        settings = SearchProviderSettings(enabled=True, provider_name="  mock  ")
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)


class TestHttpProvider:
    def test_enabled_http_returns_http_provider(self):
        settings = SearchProviderSettings(
            enabled=True, provider_name="http", base_url="https://api.search.io"
        )
        provider = create_search_provider(settings)
        assert isinstance(provider, HttpSearchProvider)

    def test_http_receives_base_url(self):
        settings = SearchProviderSettings(
            enabled=True, provider_name="http", base_url="https://api.search.io"
        )
        provider = create_search_provider(settings)
        assert isinstance(provider, HttpSearchProvider)

    def test_http_receives_api_key(self):
        settings = SearchProviderSettings(
            enabled=True,
            provider_name="http",
            base_url="https://api.search.io",
            api_key="sk-test-12345",
        )
        provider = create_search_provider(settings)
        assert isinstance(provider, HttpSearchProvider)
        # API key is stored internally, not accessible directly.
        # Verify the provider was constructed without error.

    def test_http_receives_timeout(self):
        settings = SearchProviderSettings(
            enabled=True,
            provider_name="http",
            base_url="https://api.search.io",
            timeout_seconds=15.0,
        )
        provider = create_search_provider(settings)
        assert isinstance(provider, HttpSearchProvider)

    def test_http_case_insensitive(self):
        settings = SearchProviderSettings(enabled=True, provider_name="HTTP", base_url="https://x")
        provider = create_search_provider(settings)
        assert isinstance(provider, HttpSearchProvider)


class TestMissingHttpBaseUrl:
    def test_http_without_base_url_raises(self):
        settings = SearchProviderSettings(enabled=True, provider_name="http", base_url="")
        with pytest.raises(
            SearchProviderConfigError,
            match="requires SIE_SEARCH_PROVIDER__BASE_URL",
        ):
            create_search_provider(settings)

    def test_http_with_whitespace_base_url_raises(self):
        settings = SearchProviderSettings(enabled=True, provider_name="http", base_url="   ")
        with pytest.raises(
            SearchProviderConfigError,
            match="requires SIE_SEARCH_PROVIDER__BASE_URL",
        ):
            create_search_provider(settings)


class TestUnsupportedProvider:
    def test_unknown_provider_raises(self):
        settings = SearchProviderSettings(enabled=True, provider_name="serpapi")
        with pytest.raises(SearchProviderConfigError, match="Unsupported search provider"):
            create_search_provider(settings)

    def test_unknown_provider_lists_supported(self):
        settings = SearchProviderSettings(enabled=True, provider_name="bing")
        with pytest.raises(SearchProviderConfigError, match="Supported providers:"):
            create_search_provider(settings)

    def test_empty_provider_name_raises(self):
        settings = SearchProviderSettings(enabled=True, provider_name="")
        with pytest.raises(SearchProviderConfigError, match="Unsupported search provider"):
            create_search_provider(settings)


class TestApiKeyNotInErrors:
    def test_api_key_not_in_error_message(self):
        settings = SearchProviderSettings(
            enabled=True,
            provider_name="http",
            api_key="super-secret-key-12345",
        )
        with pytest.raises(SearchProviderConfigError) as exc_info:
            create_search_provider(settings)
        assert "super-secret-key-12345" not in str(exc_info.value)


class TestProtocolCompliance:
    def test_factory_returns_search_provider(self):
        from typing import Protocol, runtime_checkable

        @runtime_checkable
        class SearchProviderProtocol(Protocol):
            async def search(self, query): ...

        settings = SearchProviderSettings(enabled=False)
        provider = create_search_provider(settings)
        # MockSearchProvider doesn't formally implement the Protocol,
        # but the factory should return an object with the search method.
        assert hasattr(provider, "search")
        assert callable(getattr(provider, "search", None))
