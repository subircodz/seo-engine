"""Tests for GEO LLM provider factory wiring (Phase 1 - Provider Registry).

Tests that the provider factory correctly creates GEOLLMProvider when
"llm" is configured as the GEO provider, and that the provider is
correctly routed through ProviderRegistry to SiteAnalysisService.
"""

from __future__ import annotations

import httpx
import pytest

from sie.config import LLMSettings, SearchProviderCapabilitySettings, SearchProviderSettings
from sie.domain.models.search import SearchDevice, SearchQuery
from sie.domain.models.search_geo import (
    GEOObservation,
    GenerativeEngineType,
)
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.ports.search_provider import SearchProvider
from sie.infrastructure.search.provider_factory import (
    _create_provider_from_capability_settings,
    create_provider_registry,
)
from sie.infrastructure.search.mock_provider import MockSearchProvider
from sie.infrastructure.search.geo_provider import GEOLLMProvider
from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider


def _query(**overrides) -> SearchQuery:
    defaults = {"query": "test keyword", "target_domain": "oursite.io"}
    defaults.update(overrides)
    return SearchQuery(**defaults)


# ══════════════════════════════════════════════════════════════════════════════
# Tests for GEO LLM Provider Factory Wiring
# ═════════════════════════════════════════════════════════════════════════════


class TestGEOLLMProviderFactoryWiring:
    """Tests that GEOLLMProvider is correctly created and wired through the provider factory."""

    def test_llm_provider_created_from_capability_settings(self):
        """Test that provider factory creates GEOLLMProvider when provider_name='llm'."""
        from sie.infrastructure.search.provider_factory import _create_provider_from_capability_settings
        from sie.config import LLMSettings

        # Create capability settings with provider_name="llm"
        cap_settings = SearchProviderCapabilitySettings(
            provider_name="llm",
            base_url="https://api.openai.com",
            api_key="test-key",
        )

        # Provide LLMSettings for LLM-specific config
        llm_settings = LLMSettings(
            base_url="https://api.openai.com",
            api_key="test-key",
            model="gpt-4o-mini",
        )

        provider = _create_provider_from_capability_settings(
            cap_settings, llm_settings=llm_settings
        )

        # Verify the provider is a GEOLLMProvider
        from sie.infrastructure.search.geo_provider import GEOLLMProvider
        assert isinstance(provider, GEOLLMProvider)
        assert provider.supports_geo is True
        assert provider.supports_aio is False

    def test_llm_provider_uses_llm_settings(self):
        """Test that GEOLLMProvider uses LLMSettings for model, temperature, etc."""
        from sie.infrastructure.search.provider_factory import _create_provider_from_capability_settings
        from sie.config import LLMSettings

        cap_settings = SearchProviderCapabilitySettings(
            provider_name="llm",
            base_url="https://api.custom-llm.com",
            api_key="custom-key",
        )

        llm_settings = LLMSettings(
            base_url="https://api.custom.com",
            api_key="custom-key",
            model="gpt-4-turbo",
            temperature=0.5,
            max_tokens=8192,
        )

        provider = _create_provider_from_capability_settings(
            cap_settings, llm_settings=llm_settings
        )

        assert isinstance(provider, GEOLLMProvider)

        # Verify the underlying LLM provider uses the correct settings
        assert provider._llm._model == "gpt-4-turbo"
        assert provider._llm._base_url == "https://api.custom-llm.com"  # From capability settings
        assert provider._llm._api_key == "custom-key"  # From capability settings


class TestGEOLLMProviderRegistryRouting:
    """Tests that GEOLLMProvider is correctly routed through ProviderRegistry."""

    async def test_registry_routes_geo_to_llm_provider(self):
        """Test that ProviderRegistry routes GEO requests to LLM provider."""
        from sie.infrastructure.search.provider_factory import create_provider_registry
        from sie.config import SearchProviderSettings, SearchProviderCapabilitySettings, LLMSettings

        # Configure settings with GEO using "llm" provider
        settings = SearchProviderSettings(
            enabled=True,
            provider_name="mock",
            rankings=None,
            aio=None,
            geo=SearchProviderCapabilitySettings(
                provider_name="llm",
                base_url="https://api.openai.com",
                api_key="test-key",
            ),
            llm=LLMSettings(
                base_url="https://api.openai.com",
                api_key="test-llm-key",
                model="gpt-4o-mini",
            ),
        )

        from sie.infrastructure.search.provider_factory import create_provider_registry
        registry = create_provider_registry(settings)

        # Verify the registry routes GEO to the LLM provider
        geo_provider = registry.get_for_geo()
        assert geo_provider is not None

        from sie.infrastructure.search.geo_provider import GEOLLMProvider
        assert isinstance(geo_provider, GEOLLMProvider), (
            f"Expected GEOLLMProvider, got {type(geo_provider)}"
        )

        # Verify AIO and rankings are None (not configured)
        assert registry.get_for_aio() is None
        assert registry.get_for_rankings() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])