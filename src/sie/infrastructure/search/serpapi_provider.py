"""SerpAPI search provider.

Implements the ``SearchProvider`` protocol for SerpAPI's GET-based API.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode, urlparse

import httpx

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.ports.search_provider import (
    SearchProviderAuthenticationError,
    SearchProviderError,
    SearchProviderRateLimit,
    SearchProviderTimeout,
)
from sie.domain.security.ssrf import validate_url
from sie.logging import get_logger

logger = get_logger(__name__)

__all__ = ["SerpApiProvider"]


class SerpApiProvider:
    """SerpAPI implementation of the ``SearchProvider`` protocol.

    Parameters
    ----------
    api_key:
        SerpAPI API key.
    timeout_seconds:
        Per-request timeout.
    connect_timeout_seconds:
        TCP connection timeout.
    read_timeout_seconds:
        Response body read timeout.
    write_timeout_seconds:
        Request body write timeout.
    pool_timeout_seconds:
        Connection pool acquisition timeout.
    client:
        Optional pre-configured ``httpx.AsyncClient`` (for testing).
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

    async def search(self, query: SearchQuery) -> SearchResult:
        """Execute a search query via SerpAPI and return provider-neutral results."""
        params = self._build_params(query)

        logger.debug("SerpAPI request query=%r", query.query)

        try:
            response = await self._client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("SerpAPI request timed out: %s", exc)
            raise SearchProviderTimeout(f"Search request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.warning("SerpAPI request transport error: %s", exc)
            raise SearchProviderError(f"Search transport error: {exc}") from exc

        if response.status_code in (401, 403):
            raise SearchProviderAuthenticationError("SerpAPI key is invalid or missing")
        if response.status_code == 429:
            raise SearchProviderRateLimit("SerpAPI rate limit exceeded")
        if response.status_code >= 400:
            body = response.text[:500]
            raise SearchProviderError(f"SerpAPI returned HTTP {response.status_code}: {body}")

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise SearchProviderError(f"SerpAPI returned invalid JSON: {exc}") from exc

        return self._parse_response(query, data)

    async def close(self) -> None:
        """Release the internally-created HTTP client (if any)."""
        if self._owns_client:
            await self._client.aclose()

    def _build_params(self, query: SearchQuery) -> dict[str, str]:
        """Serialize a ``SearchQuery`` into SerpAPI query parameters."""
        params = {
            "q": query.query,
            "gl": query.country,
            "hl": query.language,
            "device": query.device.value,
            "engine": query.search_engine,
            "num": str(query.max_results),
            "api_key": self._api_key,
        }
        return params

    def _parse_response(self, query: SearchQuery, data: object) -> SearchResult:
        """Validate and convert SerpAPI JSON into a ``SearchResult``."""
        if not isinstance(data, dict):
            raise SearchProviderError(
                f"SerpAPI response is not a JSON object, got {type(data).__name__}"
            )

        organic_results = data.get("organic_results")
        if organic_results is None:
            raise SearchProviderError("SerpAPI response missing 'organic_results' field")
        if not isinstance(organic_results, list):
            raise SearchProviderError(f"'organic_results' must be a list, got {type(organic_results).__name__}")

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

    @staticmethod
    def _parse_item(raw: dict[str, object], index: int) -> SearchResultItem | None:
        """Validate one SerpAPI organic result and return a ``SearchResultItem``."""
        # -- title --
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        # -- url --
        url = raw.get("link")
        if not isinstance(url, str) or not url.strip():
            return None
        parsed_url = urlparse(url.strip())
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            return None

        # -- position --
        position = raw.get("position")
        if isinstance(position, bool) or not isinstance(position, int):
            return None
        if position < 1:
            return None

        return SearchResultItem(position=position, title=title.strip(), url=url.strip())