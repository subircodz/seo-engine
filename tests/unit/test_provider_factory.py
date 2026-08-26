"""Tests for the search provider factory — production-ready provider behavior.

Verifies:
- Disabled provider returns MockSearchProvider
- Enabled HTTP provider requires base_url
- Enabled mock provider returns MockSearchProvider
- No silent fallback from enabled to mock
- Unsupported provider names raise errors
"""

from __future__ import annotations

import pytest

from sie.config import SearchProviderSettings
from sie.infrastructure.search.mock_provider import MockSearchProvider
from sie.infrastructure.search.provider_factory import (
    SearchProviderConfigError,
    create_search_provider,
)


class TestDisabledProvider:
    """When SIE_SEARCH_PROVIDER__ENABLED=false."""

    def test_returns_mock(self) -> None:
        settings = SearchProviderSettings(enabled=False)
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)

    def test_returns_mock_regardless_of_name(self) -> None:
        settings = SearchProviderSettings(enabled=False, provider_name="http")
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)


class TestEnabledHttpProvider:
    """When SIE_SEARCH_PROVIDER__ENABLED=true, provider_name=http."""

    def test_requires_base_url(self) -> None:
        settings = SearchProviderSettings(enabled=True, provider_name="http", base_url="")
        with pytest.raises(
            SearchProviderConfigError,
            match="requires SIE_SEARCH_PROVIDER__BASE_URL",
        ):
            create_search_provider(settings)

    def test_requires_base_url_whitespace(self) -> None:
        settings = SearchProviderSettings(enabled=True, provider_name="http", base_url="   ")
        with pytest.raises(SearchProviderConfigError):
            create_search_provider(settings)

    def test_creates_http_provider_with_url(self) -> None:
        settings = SearchProviderSettings(
            enabled=True, provider_name="http", base_url="https://api.example.com"
        )
        from sie.infrastructure.search.http_provider import HttpSearchProvider

        provider = create_search_provider(settings)
        assert isinstance(provider, HttpSearchProvider)

    def test_no_mock_fallback_when_enabled(self) -> None:
        """Critical: enabling the provider must NOT silently return a mock."""
        settings = SearchProviderSettings(enabled=True, provider_name="http", base_url="")
        with pytest.raises(SearchProviderConfigError):
            create_search_provider(settings)


class TestEnabledMockProvider:
    """When SIE_SEARCH_PROVIDER__ENABLED=true, provider_name=mock."""

    def test_returns_mock(self) -> None:
        settings = SearchProviderSettings(enabled=True, provider_name="mock")
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)


class TestUnsupportedProvider:
    """When provider_name is not in the registry."""

    def test_raises_config_error(self) -> None:
        settings = SearchProviderSettings(
            enabled=True, provider_name="bing", base_url="https://api.bing.com"
        )
        with pytest.raises(SearchProviderConfigError, match="Unsupported search provider"):
            create_search_provider(settings)
