"""Unit tests for ProviderRegistry (Phase 1).

Tests the capability-based routing logic of the ProviderRegistry.
"""

from __future__ import annotations

import pytest

from sie.domain.models.search_aio import AIOverviewObservation, AIOverviewType
from sie.domain.models.search_geo import GEOObservation, GenerativeEngineType
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.ports.search_provider import SearchProvider
from sie.infrastructure.search.provider_registry import ProviderRegistry
from sie.infrastructure.search.mock_provider import MockSearchProvider


class DummyAIOProvider:
    """A mock provider that supports AIO but not GEO."""

    supports_aio = True
    supports_geo = False

    async def search(self, query):
        return SearchResult(keyword=query.query, items=())

    async def extract_aio(self, query, target_domain):
        return AIOverviewObservation(
            keyword=query.query,
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=False,
            target_domain=target_domain,
        )

    async def query_geo(self, query, target_domain, engine_type):
        raise NotImplementedError("This provider does not support GEO")


class DummyGEOProvider:
    """A mock provider that supports GEO but not AIO."""

    supports_aio = False
    supports_geo = True

    async def search(self, query):
        return SearchResult(keyword=query.query, items=())

    async def extract_aio(self, query, target_domain):
        raise NotImplementedError("This provider does not support AIO")

    async def query_geo(self, query, target_domain, engine_type):
        return GEOObservation(
            keyword=query.query,
            engine_type=engine_type,
            target_mentioned=False,
            target_domain=target_domain,
        )


class DummyBothProvider:
    """A mock provider that supports both AIO and GEO."""

    supports_aio = True
    supports_geo = True

    async def search(self, query):
        return SearchResult(keyword=query.query, items=())

    async def extract_aio(self, query, target_domain):
        return AIOverviewObservation(
            keyword=query.query,
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=False,
            target_domain=target_domain,
        )

    async def query_geo(self, query, target_domain, engine_type):
        return GEOObservation(
            keyword=query.query,
            engine_type=engine_type,
            target_mentioned=False,
            target_domain=target_domain,
        )


class TestProviderRegistryRankings:
    """Tests for rankings provider selection."""

    def test_explicit_rankings_provider(self):
        rankings = MockSearchProvider()
        aio = DummyAIOProvider()
        registry = ProviderRegistry(rankings=rankings, aio=aio)

        assert registry.get_for_rankings() is rankings

    def test_fallback_to_default_for_rankings(self):
        default = MockSearchProvider()
        registry = ProviderRegistry(default=default)

        assert registry.get_for_rankings() is default

    def test_fallback_to_first_available_for_rankings(self):
        rankings = MockSearchProvider()
        aio = DummyAIOProvider()
        registry = ProviderRegistry(rankings=rankings, aio=aio)

        # rankings is explicitly set, should use it
        assert registry.get_for_rankings() is rankings

    def test_no_rankings_provider_returns_none(self):
        aio = DummyAIOProvider()
        registry = ProviderRegistry(aio=aio)

        assert registry.get_for_rankings() is None


class TestProviderRegistryAIO:
    """Tests for AIO provider selection."""

    def test_explicit_aio_provider(self):
        aio = DummyAIOProvider()
        registry = ProviderRegistry(aio=aio)

        assert registry.get_for_aio() is aio

    def test_fallback_to_default_if_supports_aio(self):
        default = DummyBothProvider()
        registry = ProviderRegistry(default=default)

        assert registry.get_for_aio() is default

    def test_fallback_to_first_provider_with_aio(self):
        aio = DummyAIOProvider()
        geo = DummyGEOProvider()
        registry = ProviderRegistry(aio=aio, geo=geo)

        # Should find the AIO provider
        assert registry.get_for_aio() is aio

    def test_default_without_aio_returns_none(self):
        default = DummyGEOProvider()
        registry = ProviderRegistry(default=default)

        assert registry.get_for_aio() is None

    def test_no_aio_capable_provider_returns_none(self):
        geo = DummyGEOProvider()
        registry = ProviderRegistry(geo=geo)

        assert registry.get_for_aio() is None


class TestProviderRegistryGEO:
    """Tests for GEO provider selection."""

    def test_explicit_geo_provider(self):
        geo = DummyGEOProvider()
        registry = ProviderRegistry(geo=geo)

        assert registry.get_for_geo() is geo

    def test_fallback_to_default_if_supports_geo(self):
        default = DummyBothProvider()
        registry = ProviderRegistry(default=default)

        assert registry.get_for_geo() is default

    def test_fallback_to_first_provider_with_geo(self):
        aio = DummyAIOProvider()
        geo = DummyGEOProvider()
        registry = ProviderRegistry(aio=aio, geo=geo)

        assert registry.get_for_geo() is geo

    def test_default_without_geo_returns_none(self):
        default = DummyAIOProvider()
        registry = ProviderRegistry(default=default)

        assert registry.get_for_geo() is None

    def test_no_geo_capable_provider_returns_none(self):
        aio = DummyAIOProvider()
        registry = ProviderRegistry(aio=aio)

        assert registry.get_for_geo() is None


class TestProviderRegistryBackwardCompatibility:
    """Tests for backward compatibility with single provider."""

    def test_single_provider_as_default(self):
        provider = DummyBothProvider()
        registry = ProviderRegistry(default=provider)

        assert registry.get_for_rankings() is provider
        assert registry.get_for_aio() is provider
        assert registry.get_for_geo() is provider

    def test_single_provider_without_capabilities(self):
        provider = MockSearchProvider()
        registry = ProviderRegistry(default=provider)

        assert registry.get_for_rankings() is provider
        assert registry.get_for_aio() is None
        assert registry.get_for_geo() is None

    def test_same_provider_for_multiple_capabilities(self):
        provider = DummyBothProvider()
        registry = ProviderRegistry(rankings=provider, aio=provider, geo=provider)

        assert registry.get_for_rankings() is provider
        assert registry.get_for_aio() is provider
        assert registry.get_for_geo() is provider


class TestProviderRegistryNoProviders:
    """Tests when no providers are registered."""

    def test_all_return_none(self):
        registry = ProviderRegistry()

        assert registry.get_for_rankings() is None
        assert registry.get_for_aio() is None
        assert registry.get_for_geo() is None


class TestProviderRegistryWithMockProvider:
    """Tests using MockSearchProvider with fixtures."""

    def test_mock_provider_with_aio_fixture(self):
        aio_obs = AIOverviewObservation(
            keyword="test",
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=True,
            target_domain="example.com",
        )
        mock = MockSearchProvider(aio_observations={"test": aio_obs})

        registry = ProviderRegistry(aio=mock)

        # Mock provider should be used for AIO since it has fixtures
        assert registry.get_for_aio() is mock

    def test_mock_provider_with_geo_fixture(self):
        geo_obs = GEOObservation(
            keyword="test",
            engine_type=GenerativeEngineType.CHATGPT,
            target_mentioned=True,
            target_domain="example.com",
        )
        mock = MockSearchProvider(geo_observations={("test", GenerativeEngineType.CHATGPT): geo_obs})

        registry = ProviderRegistry(geo=mock)

        assert registry.get_for_geo() is mock


if __name__ == "__main__":
    pytest.main([__file__, "-v"])