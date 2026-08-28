"""Provider Registry for capability-based search provider routing."""

from __future__ import annotations

from sie.domain.ports.search_provider import SearchProvider

__all__ = ["ProviderRegistry"]


class ProviderRegistry:
    """Registry holding multiple search providers with capability-based routing."""

    def __init__(self, *, default: SearchProvider | None = None, rankings: SearchProvider | None = None, aio: SearchProvider | None = None, geo: SearchProvider | None = None) -> None:
        self._default = default
        self._rankings = rankings
        self._aio = aio
        self._geo = geo
        self._all_providers: list[SearchProvider] = []
        for provider in (rankings, aio, geo, default):
            if provider is not None and provider not in self._all_providers:
                self._all_providers.append(provider)

    @property
    def default(self) -> SearchProvider | None:
        return self._default

    @property
    def rankings_provider(self) -> SearchProvider | None:
        return self._rankings or self._default

    @property
    def aio_provider(self) -> SearchProvider | None:
        if self._aio is not None:
            return self._aio
        if self._default is not None and getattr(self._default, "supports_aio", False):
            return self._default
        return next((p for p in self._all_providers if getattr(p, "supports_aio", False)), None)

    @property
    def geo_provider(self) -> SearchProvider | None:
        if self._geo is not None:
            return self._geo
        if self._default is not None and getattr(self._default, "supports_geo", False):
            return self._default
        return next((p for p in self._all_providers if getattr(p, "supports_geo", False)), None)

    def get_for_rankings(self) -> SearchProvider | None:
        return self.rankings_provider

    def get_for_aio(self) -> SearchProvider | None:
        return self.aio_provider

    def get_for_geo(self) -> SearchProvider | None:
        return self.geo_provider

    def get_aio_providers(self) -> list[SearchProvider]:
        providers: list[SearchProvider] = []
        seen: set[int] = set()
        for provider in (self._aio, self._default, *self._all_providers):
            if provider is not None and getattr(provider, "supports_aio", False) and id(provider) not in seen:
                seen.add(id(provider))
                providers.append(provider)
        return providers

    async def close(self) -> None:
        """Close all providers that own network or cache resources."""
        for provider in self._all_providers:
            close = getattr(provider, "close", None)
            if close is not None:
                await close()
