"""SerpAPI search provider with AIO extraction support."""

from __future__ import annotations

import json
from urllib.parse import urlparse

import httpx

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_aio import (
    AIOCitation,
    AIOverviewObservation,
    AIOverviewType,
    CitationSource,
)
from sie.domain.models.search_geo import GenerativeEngineType, GEOObservation
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.ports.search_provider import (
    SearchProviderAuthenticationError,
    SearchProviderCapabilityError,
    SearchProviderError,
    SearchProviderRateLimit,
    SearchProviderTimeout,
)
from sie.infrastructure.search.quota_tracker import QuotaExceeded, QuotaTracker
from sie.infrastructure.search.response_cache import CacheKey, SearchResponseCache
from sie.logging import get_logger

logger = get_logger(__name__)

__all__ = ["SerpApiProvider"]


class SerpApiProvider:
    """SerpAPI implementation of the ``SearchProvider`` protocol.

    Cache and quota policies are constructor-injected so provider pricing and
    limits never become hard-coded application behaviour.
    """

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 30.0,
        write_timeout_seconds: float = 10.0,
        pool_timeout_seconds: float = 5.0,
        quota_cost_per_request_usd: float = 0.0,
        monthly_request_limit: int = 0,
        cache_max_entries: int = 5000,
        cache_ttl_seconds: float = 86400.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise SearchProviderError("SerpAPI requires an API key")

        self._api_key = api_key
        self._base_url = "https://serpapi.com/search"
        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

        self._quota = QuotaTracker(
            provider_name="serpapi",
            cost_per_request_usd=quota_cost_per_request_usd,
            monthly_request_limit=monthly_request_limit,
        )
        self._cache = SearchResponseCache(
            max_entries=cache_max_entries,
            ttl_seconds=cache_ttl_seconds,
        )
        # AIO is a distinct representation of the same SERP request. Keep a
        # separate cache so a ranking lookup and an AIO lookup cannot corrupt
        # each other's value types.
        self._aio_cache = SearchResponseCache(
            max_entries=cache_max_entries,
            ttl_seconds=cache_ttl_seconds,
        )

    @property
    def supports_aio(self) -> bool:
        return True

    @property
    def supports_geo(self) -> bool:
        return False

    def _cache_key(self, query: SearchQuery) -> CacheKey:
        return CacheKey.from_query(
            keyword=query.query,
            country=query.country,
            language=query.language,
            device=query.device.value,
            provider="serpapi",
            search_engine=query.search_engine,
        )

    async def search(self, query: SearchQuery) -> SearchResult:
        """Execute a search query via SerpAPI and return provider-neutral results."""
        cache_key = self._cache_key(query)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("SerpAPI cache hit for query=%r", query.query)
            return cached

        data = await self._request_json(self._build_params(query))
        result = self._parse_response(query, data)
        self._cache.put(cache_key, result)
        return result

    async def extract_aio(
        self, query: SearchQuery, target_domain: str
    ) -> AIOverviewObservation | None:
        """Extract AIO from the same SERP request, with independent caching."""
        cache_key = self._cache_key(query)
        cached = self._aio_cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._request_json(self._build_params(query))
        observation = self._parse_aio_response(query.query, target_domain, data)
        self._aio_cache.put(cache_key, observation)
        return observation

    async def _request_json(self, params: dict[str, str]) -> dict:
        """Perform exactly one billable outbound request and parse its JSON body."""
        try:
            self._quota.reserve()
        except QuotaExceeded as exc:
            logger.warning("SerpAPI local quota exhausted: %s", exc)
            raise SearchProviderRateLimit(str(exc)) from exc

        try:
            response = await self._client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            self._quota.record_request(success=False)
            logger.warning("SerpAPI request timed out: %s", exc)
            raise SearchProviderTimeout(f"Search request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            self._quota.record_request(success=False)
            logger.warning("SerpAPI request transport error: %s", exc)
            raise SearchProviderError(f"Search transport error: {exc}") from exc

        if response.status_code in (401, 403):
            self._quota.record_request(success=False)
            raise SearchProviderAuthenticationError("SerpAPI key is invalid or missing")
        if response.status_code == 429:
            self._quota.record_request(rate_limited=True)
            raise SearchProviderRateLimit("SerpAPI rate limit exceeded")
        if response.status_code >= 400:
            self._quota.record_request(success=False)
            body = response.text[:500]
            raise SearchProviderError(f"SerpAPI returned HTTP {response.status_code}: {body}")

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            self._quota.record_request(success=False)
            raise SearchProviderError(f"SerpAPI returned invalid JSON: {exc}") from exc

        if not isinstance(data, dict):
            self._quota.record_request(success=False)
            raise SearchProviderError(
                f"SerpAPI response is not a JSON object, got {type(data).__name__}"
            )

        self._quota.record_request(success=True)
        return data

    async def query_geo(
        self, query: SearchQuery, target_domain: str, engine_type: GenerativeEngineType
    ) -> GEOObservation | None:
        raise SearchProviderCapabilityError(
            f"SerpApiProvider does not support GEO queries for engine {engine_type.value}"
        )

    @property
    def quota(self) -> QuotaTracker:
        return self._quota

    @property
    def stats(self) -> dict[str, object]:
        """Expose provider cache/quota telemetry without exposing credentials."""
        return {
            "quota": self._quota.snapshot(),
            "search_cache": self._cache.stats,
            "aio_cache": self._aio_cache.stats,
        }

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _build_params(self, query: SearchQuery) -> dict[str, str]:
        return {
            "q": query.query,
            "gl": query.country,
            "hl": query.language,
            "device": query.device.value,
            "engine": query.search_engine,
            "num": str(query.max_results),
            "api_key": self._api_key,
        }

    def _parse_response(self, query: SearchQuery, data: object) -> SearchResult:
        if not isinstance(data, dict):
            raise SearchProviderError(
                f"SerpAPI response is not a JSON object, got {type(data).__name__}"
            )
        organic_results = data.get("organic_results")
        if organic_results is None:
            raise SearchProviderError("SerpAPI response missing 'organic_results' field")
        if not isinstance(organic_results, list):
            raise SearchProviderError(
                f"'organic_results' must be a list, got {type(organic_results).__name__}"
            )

        items: list[SearchResultItem] = []
        for idx, raw_item in enumerate(organic_results):
            if not isinstance(raw_item, dict):
                continue
            item = self._parse_item(raw_item, idx)
            if item is not None:
                items.append(item)

        return SearchResult(
            keyword=query.query,
            search_engine=query.search_engine,
            country=query.country,
            language=query.language,
            device=query.device,
            items=tuple(items),
        )

    def _parse_aio_response(
        self, keyword: str, target_domain: str, data: dict
    ) -> AIOverviewObservation:
        ai_overview = data.get("ai_overview")
        if not ai_overview or not isinstance(ai_overview, dict):
            return AIOverviewObservation(
                keyword=keyword,
                ai_type=AIOverviewType.AI_OVERVIEW,
                present=False,
                target_cited=False,
                target_domain=target_domain,
                citation_count=0,
                citations=(),
                competitor_cited_domains=(),
                source="serpapi",
            )

        citations = []
        competitor_domains = set()
        target_cited = False
        raw_citations = ai_overview.get("citations")
        if isinstance(raw_citations, list):
            for idx, cite in enumerate(raw_citations):
                if not isinstance(cite, dict):
                    continue
                cite_url = cite.get("link") or cite.get("url")
                cite_title = cite.get("title") or ""
                if not isinstance(cite_url, str) or not cite_url:
                    continue
                parsed = urlparse(cite_url)
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    continue
                domain = parsed.netloc.split(":")[0].casefold().removeprefix("www.")
                citation = AIOCitation(
                    domain=domain,
                    url=cite_url,
                    position=idx,
                    source_type=CitationSource.WEB_PAGE,
                    title=cite_title if isinstance(cite_title, str) else "",
                )
                citations.append(citation)
                if domain == target_domain.casefold().removeprefix("www."):
                    target_cited = True
                else:
                    competitor_domains.add(domain)

        return AIOverviewObservation(
            keyword=keyword,
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=True,
            target_cited=target_cited,
            target_domain=target_domain,
            citation_count=len(citations),
            citations=tuple(citations),
            competitor_cited_domains=tuple(sorted(competitor_domains)),
            source="serpapi",
        )

    @staticmethod
    def _parse_item(raw: dict[str, object], index: int) -> SearchResultItem | None:
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        url = raw.get("link")
        if not isinstance(url, str) or not url.strip():
            return None
        parsed_url = urlparse(url.strip())
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            return None
        position = raw.get("position")
        if isinstance(position, bool) or not isinstance(position, int) or position < 1:
            return None
        return SearchResultItem(position=position, title=title.strip(), url=url.strip())
