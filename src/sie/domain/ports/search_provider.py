"""Port: search provider abstraction (Phase 6H + AIO/GEO extensions).

Domain layer depends on this Protocol; concrete implementations live in
``sie.infrastructure.search`` and are injected at the composition root.

The provider exposes a minimal async ``search`` interface that returns
provider-neutral ``SearchResult`` objects.  Domain code never references
Google, Bing, SerpAPI, or any vendor SDK.

Extended with:
- AIO (AI Overview) extraction capability
- GEO (Generative Engine) observation capability
"""

from __future__ import annotations

from typing import Protocol

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_aio import AIOverviewObservation
from sie.domain.models.search_geo import GenerativeEngineType, GEOObservation
from sie.domain.models.search_result import SearchResult


class SearchProvider(Protocol):
    """Thin async interface for executing a single search query."""

    async def search(self, query: SearchQuery) -> SearchResult:
        """Execute ``query`` and return provider-neutral results.

        Raises ``SearchProviderError`` (or a subclass) on failure.
        """
        ...

    @property
    def supports_aio(self) -> bool:
        """Whether this provider can extract AI Overview data."""
        ...

    @property
    def supports_geo(self) -> bool:
        """Whether this provider can query generative engines."""
        ...

    async def extract_aio(
        self, query: SearchQuery, target_domain: str
    ) -> AIOverviewObservation | None:
        """Extract AI Overview observation for a query.

        Returns ``None`` if the provider does not support AIO extraction
        or if the data is unavailable.

        Implementations should return an observation with ``present=False``
        if no AI Overview was detected, and ``present=True`` with citations
        if one was found.

        Raises ``SearchProviderError`` on transport failure.
        """
        ...

    async def query_geo(
        self, query: SearchQuery, target_domain: str, engine_type: GenerativeEngineType
    ) -> GEOObservation | None:
        """Query a generative engine for brand/entity mentions.

        Returns ``None`` if the provider does not support GEO queries
        or if the data is unavailable.

        Raises ``SearchProviderError`` on transport failure.
        """
        ...


# ═════════════════════════════════════════════════════════════════════════════
# Provider-neutral errors
# ═════════════════════════════════════════════════════════════════════════════


class SearchProviderError(Exception):
    """Raised when a search provider cannot fulfil a request.

    Subclasses distinguish error categories without leaking transport or
    vendor-specific details into the domain layer.
    """


class SearchProviderTimeout(SearchProviderError):
    """The search request timed out."""


class SearchProviderRateLimit(SearchProviderError):
    """The provider returned a rate-limit (429) response."""


class SearchProviderAuthenticationError(SearchProviderError):
    """The API key is missing, invalid, or expired."""


class SearchProviderCapabilityError(SearchProviderError):
    """Raised when a provider does not support a requested capability."""
