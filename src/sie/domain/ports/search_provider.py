"""Port: search provider abstraction (Phase 6H).

Domain layer depends on this Protocol; concrete implementations live in
``sie.infrastructure.search`` and are injected at the composition root.

The provider exposes a minimal async ``search`` interface that returns
provider-neutral ``SearchResult`` objects.  Domain code never references
Google, Bing, SerpAPI, or any vendor SDK.
"""

from typing import Protocol

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_result import SearchResult


class SearchProvider(Protocol):
    """Thin async interface for executing a single search query."""

    async def search(self, query: SearchQuery) -> SearchResult:
        """Execute ``query`` and return provider-neutral results.

        Raises ``SearchProviderError`` (or a subclass) on failure.
        """
        ...


# ════════════════════════════════════════════════════════════════════════════
# Provider-neutral errors
# ════════════════════════════════════════════════════════════════════════════


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
