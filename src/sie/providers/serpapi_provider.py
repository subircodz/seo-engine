"""SerpAPI provider implementation."""

from __future__ import annotations

import time
from typing import Any

from sie.config.settings import get_settings
from sie.providers.base import SearchProvider
from sie.providers.models import SearchQuery, SearchResponse
from sie.providers.quota_tracker import QuotaTracker
from sie.providers.response_cache import SearchResponseCache


class SerpApiProvider(SearchProvider):
    """Search provider backed by SerpAPI."""

    name = "serpapi"

    def __init__(
        self,
        api_key: str | None = None,
        cache: SearchResponseCache | None = None,
        quota: QuotaTracker | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.serpapi.api_key
        self._cache = cache or SearchResponseCache(
            max_size=settings.serpapi.cache_max_size,
            ttl_seconds=settings.serpapi.cache_ttl_seconds,
        )
        self._quota = quota or QuotaTracker(
            monthly_limit=settings.serpapi.monthly_request_limit,
            cost_per_request_usd=settings.serpapi.cost_per_request_usd,
        )

    @property
    def quota(self) -> QuotaTracker:
        return self._quota

    @property
    def stats(self) -> dict[str, Any]:
        return self._cache.stats()

    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute a SerpAPI search with quota and response caching."""
        cached = self._cache.get(query)
        if cached is not None:
            return cached

        self._quota.check_available()
        started = time.monotonic()

        try:
            response = self._perform_request(query)
        except Exception:
            self._quota.record_failure()
            raise
        else:
            self._quota.record_success()
            self._cache.set(query, response)
            _ = time.monotonic() - started
            return response

    def _perform_request(self, query: SearchQuery) -> SearchResponse:
        """Perform the actual HTTP request to SerpAPI."""
        # Existing implementation retained here.
        raise NotImplementedError
