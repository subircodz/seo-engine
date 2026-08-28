"""Search provider factory with capability routing and production caching."""

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


class SearchProviderConfigError(Exception):
    """Raised when the search provider cannot be constructed from config."""


def _create_mock(
    settings: SearchProviderSettings | SearchProviderCapabilitySettings,
) -> SearchProvider:
    from sie.infrastructure.search.mock_provider import MockSearchProvider

    return MockSearchProvider()


def _create_http(
    settings: SearchProviderSettings | SearchProviderCapabilitySettings,
) -> SearchProvider:
    if not settings.base_url or not settings.base_url.strip():
        raise SearchProviderConfigError("Search provider 'http' requires a base URL")
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
    *,
    request_cost_usd: float = 0.0,
    monthly_request_limit: int = 0,
) -> SearchProvider:
    if not settings.api_key or not settings.api_key.strip():
        raise SearchProviderConfigError("Search provider 'serpapi' requires an API key")
    from sie.infrastructure.search.serpapi_provider import SerpApiProvider

    return SerpApiProvider(
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        write_timeout_seconds=settings.write_timeout_seconds,
        pool_timeout_seconds=settings.pool_timeout_seconds,
        quota_cost_per_request_usd=request_cost_usd,
        monthly_request_limit=monthly_request_limit,
    )


def _create_valueserp(
    settings: SearchProviderSettings | SearchProviderCapabilitySettings,
) -> SearchProvider:
    if not settings.api_key or not settings.api_key.strip():
        raise SearchProviderConfigError("Search provider 'valueserp' requires an API key")
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
    if not settings.base_url or not settings.base_url.strip():
        raise SearchProviderConfigError("Search provider 'llm' requires a base URL")
    if not settings.api_key or not settings.api_key.strip():
        raise SearchProviderConfigError("Search provider 'llm' requires an API key")

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


def _wrap_distributed_cache(provider: SearchProvider, settings) -> SearchProvider:
    """Add shared Redis caching when explicitly enabled.

    Redis is an L2 cache. Provider-local caches remain useful as the L1 cache.
    If Redis is unavailable, the provider continues to function using its local
    cache rather than turning a cache outage into a search outage.
    """
    from sie.infrastructure.search.distributed_cache_provider import DistributedCacheSearchProvider
    from sie.infrastructure.search.redis_response_cache import RedisSearchResponseCache

    if not getattr(settings, "enabled", False):
        return provider
    cache_cfg = settings._cache_settings if hasattr(settings, "_cache_settings") else None
    if cache_cfg is None or not cache_cfg.enabled:
        return provider
    cache = RedisSearchResponseCache(
        cache_cfg.redis_url,
        prefix=f"{cache_cfg.key_prefix}search:",
        ttl_seconds=cache_cfg.response_ttl_seconds,
    )
    return DistributedCacheSearchProvider(provider, cache)


def _create_provider_from_capability_settings(
    settings: SearchProviderCapabilitySettings,
    *,
    llm_settings: LLMSettings | None = None,
    serpapi_request_cost_usd: float = 0.0,
    serpapi_monthly_request_limit: int = 0,
    cache_settings=None,
) -> SearchProvider:
    if not settings.provider_name or settings.provider_name.lower().strip() == "mock":
        provider = _create_mock(settings)
    else:
        name = settings.provider_name.lower().strip()
        entry = _REGISTRY.get(name)
        if entry is None:
            raise SearchProviderConfigError(
                f"Unsupported search provider: {settings.provider_name!r}. "
                f"Supported providers: {', '.join(sorted(_REGISTRY))}"
            )
        _label, factory = entry
        logger.info("Capability provider enabled: name=%s base_url=%s", name, settings.base_url)
        if name == "llm":
            provider = factory(settings, llm_settings=llm_settings)
        elif name == "serpapi":
            provider = factory(
                settings,
                request_cost_usd=serpapi_request_cost_usd,
                monthly_request_limit=serpapi_monthly_request_limit,
            )
        else:
            provider = factory(settings)
    if cache_settings is not None and cache_settings.enabled:
        cache_settings_holder = type(
            "CacheSettingsHolder", (), {"_cache_settings": cache_settings, "enabled": True}
        )()
        provider = _wrap_distributed_cache(provider, cache_settings_holder)
    return provider


def create_search_provider(
    settings: SearchProviderSettings,
    *,
    serpapi_request_cost_usd: float = 0.0,
    serpapi_monthly_request_limit: int = 0,
    cache_settings=None,
) -> SearchProvider:
    """Construct one provider from explicit settings.

    All runtime settings are passed explicitly; the factory never re-reads the
    process singleton, which keeps tests and multi-tenant composition correct.
    """
    if not settings.enabled:
        return _create_mock(settings)
    name = settings.provider_name.lower().strip()
    entry = _REGISTRY.get(name)
    if entry is None:
        raise SearchProviderConfigError(
            f"Unsupported search provider: {settings.provider_name!r}. "
            f"Supported providers: {', '.join(sorted(_REGISTRY))}"
        )
    _label, factory = entry
    if name == "serpapi":
        provider = factory(
            settings,
            request_cost_usd=serpapi_request_cost_usd,
            monthly_request_limit=serpapi_monthly_request_limit,
        )
    else:
        provider = factory(settings)
    if cache_settings is not None and cache_settings.enabled:
        cache_settings_holder = type(
            "CacheSettingsHolder", (), {"_cache_settings": cache_settings, "enabled": True}
        )()
        provider = _wrap_distributed_cache(provider, cache_settings_holder)
    return provider


def create_provider_registry(
    settings: SearchProviderSettings, *, serpapi_settings=None, cache_settings=None
) -> ProviderRegistry:
    """Construct a capability-routed provider registry from explicit settings."""
    if not settings.enabled:
        return ProviderRegistry(default=_create_mock(settings))

    has_capability_settings = any(
        s is not None for s in (settings.rankings, settings.aio, settings.geo)
    )
    if not has_capability_settings:
        provider = create_search_provider(
            settings,
            serpapi_request_cost_usd=serpapi_settings.request_cost_usd if serpapi_settings else 0.0,
            serpapi_monthly_request_limit=serpapi_settings.monthly_request_limit
            if serpapi_settings
            else 0,
            cache_settings=cache_settings,
        )
        return ProviderRegistry(default=provider)

    providers: dict[str, SearchProvider] = {}
    for cap_name, cap_settings in {
        "rankings": settings.rankings,
        "aio": settings.aio,
        "geo": settings.geo,
    }.items():
        if cap_settings is None:
            continue
        providers[cap_name] = _create_provider_from_capability_settings(
            cap_settings,
            llm_settings=settings.llm if cap_name == "geo" else None,
            serpapi_request_cost_usd=serpapi_settings.request_cost_usd if serpapi_settings else 0.0,
            serpapi_monthly_request_limit=serpapi_settings.monthly_request_limit
            if serpapi_settings
            else 0,
            cache_settings=cache_settings,
        )
    return ProviderRegistry(
        rankings=providers.get("rankings"),
        aio=providers.get("aio"),
        geo=providers.get("geo"),
        default=None,
    )
