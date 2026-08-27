"""Provider Registry for capability-based search provider routing.

This module provides the ``ProviderRegistry`` class that holds multiple
``SearchProvider`` instances and routes capability requests (rankings, AIO, GEO)
to the appropriate provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sie.domain.ports.search_provider import SearchProvider

if TYPE_CHECKING:
    pass

__all__ = ["ProviderRegistry"]


class ProviderRegistry:
    """Registry holding multiple search providers with capability-based routing.

    The registry allows different capabilities (rankings, AIO, GEO) to be served
    by different providers. When a capability-specific provider is not configured,
    it falls back to the default provider.

    Parameters
    ----------
    default:
        The default provider used as fallback for all capabilities.
        For backward compatibility, a single provider can be passed here.
    rankings:
        Provider for search/ranking collection. Falls back to ``default``.
    aio:
        Provider for AI Overview extraction. Falls back to ``default`` if it
        supports AIO, otherwise searches for any registered provider that
        supports AIO.
    geo:
        Provider for Generative Engine queries. Falls back to ``default`` if it
        supports GEO, otherwise searches for any registered provider that
        supports GEO.
    """

    def __init__(
        self,
        *,
        default: SearchProvider | None = None,
        rankings: SearchProvider | None = None,
        aio: SearchProvider | None = None,
        geo: SearchProvider | None = None,
    ) -> None:
        self._default = default
        self._rankings = rankings
        self._aio = aio
        self._geo = geo

        # Build a list of all registered providers for fallback searches
        self._all_providers: list[SearchProvider] = []
        for p in (rankings, aio, geo, default):
            if p is not None and p not in self._all_providers:
                self._all_providers.append(p)

    @property
    def default(self) -> SearchProvider | None:
        """The default provider (fallback for all capabilities)."""
        return self._default

    @property
    def rankings_provider(self) -> SearchProvider | None:
        """Provider explicitly configured for rankings, or default."""
        return self._rankings or self._default

    @property
    def aio_provider(self) -> SearchProvider | None:
        """Provider explicitly configured for AIO, or fallback."""
        if self._aio is not None:
            return self._aio
        if self._default is not None and getattr(self._default, "supports_aio", False):
            return self._default
        for p in self._all_providers:
            if getattr(p, "supports_aio", False):
                return p
        return None

    @property
    def geo_provider(self) -> SearchProvider | None:
        """Provider explicitly configured for GEO, or fallback."""
        if self._geo is not None:
            return self._geo
        if self._default is not None and getattr(self._default, "supports_geo", False):
            return self._default
        for p in self._all_providers:
            if getattr(p, "supports_geo", False):
                return p
        return None

    def get_for_rankings(self) -> SearchProvider | None:
        """Get the provider for search/ranking collection.

        Returns the rankings-specific provider, falling back to default.
        Returns ``None`` if no provider is available.
        """
        return self.rankings_provider

    def get_for_aio(self) -> SearchProvider | None:
        """Get the provider for AI Overview extraction.

        Returns the AIO-specific provider, or a provider that supports AIO.
        Returns ``None`` if no AIO-capable provider is available.
        """
        return self.aio_provider

    def get_for_geo(self) -> SearchProvider | None:
        """Get the provider for Generative Engine queries.

        Returns the GEO-specific provider, or a provider that supports GEO.
        Returns ``None`` if no GEO-capable provider is available.
        """
        return self.geo_provider
