"""Search provider factory (Phase 6L + Provider Registry + GEO LLM).

Centralises provider selection so the composition root (``app.py``) no
longer contains branching logic for provider construction.

The factory reads ``SearchProviderSettings`` and returns a concrete
``SearchProvider`` implementation or a ``ProviderRegistry``:

- ``enabled=False``  → ``MockSearchProvider`` (or registry with mock)
- ``enabled=True``   → dispatch on ``provider_name`` (
      ``"mock"``, ``"http"``, ``"serpapi"``, ``"llm"``
  )
- capability-specific settings → ``ProviderRegistry`` with multiple providers
- unsupported name   → raise ``SearchProviderConfigError``

All providers live in ``sie.infrastructure.search``; the domain layer
never sees this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sie.config import LLMSettings, SearchProviderCapabilitySettings, SearchProviderSettings
from sie.domain.ports.search_provider import SearchProvider
from sie.infrastructure.search.provider_registry import ProviderRegistry
from sie.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

__all__ = [
    "SearchProviderConfigError",
    "create_provider_registry",
    "create_search_provider",
]

# Registry mapping provider names → lazy import callables.
# Each callable receives ``SearchProviderSettings`` (or capability settings) and returns a
# ``SearchProvider``.  Lazy imports keep heavy dependencies (e.g. httpx)
# out of the import path when they are not needed.


def _create_mock(
    settings: SearchProviderSettings | SearchProviderCapabilitySettings,
) -> SearchProvider:
    from sie.infrastructure.search.mock_provider import MockSearchProvider

    return MockSearchProvider()


def _create_http(
    settings: SearchProviderSettings | SearchProviderCapabilitySettings,
) -> SearchProvider:
    if not settings.base_url or not settings.base_url.strip():
        raise SearchProviderConfigError(
            "Search provider 'http' requires SIE_SEARCH_PROVIDER__BASE_URL"
        )
    from sie.infrastructure.search.http_provider import HttpSearchProvider

    return HttpSearchProvider(
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        write_timeout_seconds=settings.write_timeout_seconds,
        pool_timeout_seconds=settings.pool_timeout_seconds,
        allow_localhost=settings.allow_localhost,
    )


def _create_serpapi(
    settings: SearchProviderSettings | SearchProviderCapabilitySettings,
) -> SearchProvider:
    if not settings.api_key or not settings.api_key.strip():
        raise SearchProviderConfigError(
            "Search provider 'serpapi' requires SIE_SEARCH_PROVIDER__API_KEY"
        )
    from sie.infrastructure.search.serpapi_provider import SerpApiProvider

    return SerpApiProvider(
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        write_timeout_seconds=settings.write_timeout_seconds,
        pool_timeout_seconds=settings.pool_timeout_seconds,
    )


def _create_valueserp(
    settings: SearchProviderSettings | SearchProviderCapabilitySettings,
) -> SearchProvider:
    if not settings.api_key or not settings.api_key.strip():
        raise SearchProviderConfigError(
            "Search provider 'valueserp' requires SIE_SEARCH_PROVIDER__API_KEY"
        )
    from sie.infrastructure.search.valueserp_provider import ValueSerpProvider

    return ValueSerpProvider(
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        write_timeout_seconds=settings.write_timeout_seconds,
        pool_timeout_seconds=settings.pool_timeout_seconds,
    )


def _create_llm(
    settings: SearchProviderSettings | SearchProviderCapabilitySettings,
    *,
    llm_settings: LLMSettings | None = None,
) -> SearchProvider:
    """Create a GEO LLM provider using OpenAI-compatible LLM."""
    if not settings.base_url or not settings.base_url.strip():
        raise SearchProviderConfigError(
            "Search provider 'llm' requires SIE_SEARCH_PROVIDER__BASE_URL"
        )
    if not settings.api_key or not settings.api_key.strip():
        raise SearchProviderConfigError(
            "Search provider 'llm' requires SIE_SEARCH_PROVIDER__API_KEY"
        )

    # Use LLMSettings for LLM-specific config (model, temperature, etc.)
    # Fall back to capability settings for base_url and api_key
    llm = LLMSettings(
        enabled=True,
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=llm_settings.model if llm_settings else "gpt-4o-mini",
        temperature=llm_settings.temperature if llm_settings else 0.3,
        max_tokens=llm_settings.max_tokens if llm_settings else 4096,
        timeout_seconds=llm_settings.timeout_seconds if llm_settings else 60.0,
        connect_timeout_seconds=llm_settings.connect_timeout_seconds if llm_settings else 10.0,
        read_timeout_seconds=llm_settings.read_timeout_seconds if llm_settings else 60.0,
        write_timeout_seconds=llm_settings.write_timeout_seconds if llm_settings else 30.0,
        pool_timeout_seconds=llm_settings.pool_timeout_seconds if llm_settings else 10.0,
    )

    from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider
    from sie.infrastructure.search.geo_provider import GEOLLMProvider

    llm_provider = OpenAICompatibleProvider(
        base_url=llm.base_url,
        api_key=llm.api_key,
        model=llm.model,
        timeout_seconds=llm.timeout_seconds,
        connect_timeout_seconds=llm.connect_timeout_seconds,
        read_timeout_seconds=llm.read_timeout_seconds,
        write_timeout_seconds=llm.write_timeout_seconds,
        pool_timeout_seconds=llm.pool_timeout_seconds,
    )

    return GEOLLMProvider(llm_provider=llm_provider)


_REGISTRY: dict[str, tuple[str, object]] = {
    "mock": ("MockSearchProvider", _create_mock),
    "http": ("HttpSearchProvider", _create_http),
    "serpapi": ("SerpApiProvider", _create_serpapi),
    "valueserp": ("ValueSerpProvider", _create_valueserp),
    "llm": ("GEOLLMProvider", _create_llm),
}


class SearchProviderConfigError(Exception):
    """Raised when the search provider cannot be constructed from config."""


def _create_provider_from_capability_settings(
    settings: SearchProviderCapabilitySettings,
    *,
    llm_settings: LLMSettings | None = None,
) -> SearchProvider:
    """Create a provider from capability-specific settings.

    Uses the same logic as the main factory but with capability-specific settings.
    Falls back to mock if provider_name is 'mock' or settings are empty.
    """
    if not settings.provider_name or settings.provider_name.lower().strip() == "mock":
        return _create_mock(settings)

    name = settings.provider_name.lower().strip()
    entry = _REGISTRY.get(name)
    if entry is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise SearchProviderConfigError(
            f"Unsupported search provider: {settings.provider_name!r}. "
            f"Supported providers: {supported}"
        )

    _label, factory = entry
    logger.info("Capability provider enabled: name=%s base_url=%s", name, settings.base_url)

    # Special handling for LLM provider which needs LLMSettings
    if name == "llm":
        return factory(settings, llm_settings=llm_settings)

    return factory(settings)


def create_search_provider(settings: SearchProviderSettings) -> SearchProvider:
    """Construct and return a ``SearchProvider`` from *settings*.

    Behaviour
    ---------
    - When ``settings.enabled`` is ``False`` the factory always returns
      a ``MockSearchProvider`` regardless of ``provider_name``.
    - When ``enabled`` is ``True`` the ``provider_name`` is looked up
      in the registry.  An unsupported name raises
      ``SearchProviderConfigError``.

    No API keys are exposed in log messages or error strings.

    Raises
    ------
    SearchProviderConfigError
        When the provider is enabled but misconfigured (missing base_url,
        unsupported provider_name, etc.).
    """
    if not settings.enabled:
        logger.info(
            "Search provider disabled — mock provider active. "
            "Set SIE_SEARCH_PROVIDER__ENABLED=true for real SERP data."
        )
        return _create_mock(settings)

    name = settings.provider_name.lower().strip()

    entry = _REGISTRY.get(name)
    if entry is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise SearchProviderConfigError(
            f"Unsupported search provider: {settings.provider_name!r}. "
            f"Supported providers: {supported}"
        )

    _label, factory = entry
    logger.info("Search provider enabled: name=%s base_url=%s", name, settings.base_url)
    return factory(settings)


def create_provider_registry(settings: SearchProviderSettings) -> ProviderRegistry:
    """Construct a ``ProviderRegistry`` from *settings*.

    Creates providers for each capability (rankings, AIO, GEO) based on
    capability-specific settings, falling back to legacy single-provider settings.

    Behaviour
    ---------
    - When ``settings.enabled`` is ``False``: returns a registry with a single
      ``MockSearchProvider`` as default.
    - When ``enabled`` is ``True``:
      - Creates providers for each capability from their specific settings
      - Falls back to legacy settings for capabilities without specific config
      - Reuses provider instances when the same configuration is used
    - When legacy settings are used (no capability-specific config):
      creates a single provider and uses it as default for all capabilities.

    Raises
    ------
    SearchProviderConfigError
        When a provider is enabled but misconfigured.
    """
    # If disabled, return registry with mock provider
    if not settings.enabled:
        logger.info(
            "Search provider disabled — mock provider active. "
            "Set SIE_SEARCH_PROVIDER__ENABLED=true for real SERP data."
        )
        mock = _create_mock(settings)
        return ProviderRegistry(default=mock)

    # Check if any capability-specific settings are provided
    has_capability_settings = any(
        s is not None for s in (settings.rankings, settings.aio, settings.geo)
    )

    # If no capability-specific settings, use legacy single-provider behavior
    if not has_capability_settings:
        provider = create_search_provider(settings)
        logger.info("Using legacy single-provider mode for all capabilities")
        return ProviderRegistry(default=provider)

    # Build providers for each capability
    providers: dict[str, SearchProvider] = {}
    capability_settings = {
        "rankings": settings.rankings,
        "aio": settings.aio,
        "geo": settings.geo,
    }

    for cap_name, cap_settings in capability_settings.items():
        if cap_settings is not None:
            # Pass LLMSettings for GEO capability to configure LLM provider
            llm_settings = settings.llm if cap_name == "geo" else None
            providers[cap_name] = _create_provider_from_capability_settings(
                cap_settings, llm_settings=llm_settings
            )
            logger.info("Created %s provider: %s", cap_name, type(providers[cap_name]).__name__)

    # For capabilities without specific settings, they will fall back via ProviderRegistry logic
    return ProviderRegistry(
        rankings=providers.get("rankings"),
        aio=providers.get("aio"),
        geo=providers.get("geo"),
        default=None,  # No global default; fallbacks handled by ProviderRegistry
    )
