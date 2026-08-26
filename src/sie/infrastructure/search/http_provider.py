"""Generic HTTP search provider (Phase 6K + AIO/GEO).

Implements the ``SearchProvider`` protocol for any API that exposes a
``POST /search`` endpoint returning provider-neutral JSON results.

This adapter is vendor-agnostic: it does not know which search engine or
ranking service backs the endpoint.  The contract is intentionally minimal
so that future real providers (SerpAPI, DataForSEO, etc.) only need to
implement a thin translation layer on top of this, or the upstream API
can be made to conform to this contract via a small proxy.

Generic HTTP Contract
---------------------

**Request** (POST ``{base_url}/search``)::

    {
        "query": "best crm software",
        "country": "us",
        "language": "en",
        "device": "desktop",
        "search_engine": "google",
        "target_domain": "example.com",   // omitted when None
        "max_results": 10
    }

**Response** (200 OK)::

    {
        "results": [
            {"title": "Example CRM", "url": "https://example.com/crm", "position": 1},
            {"title": "Other CRM",   "url": "https://other.com/crm",  "position": 2}
        ]
    }

Authentication
--------------
When ``api_key`` is non-empty the adapter sends an ``Authorization: Bearer``
header.  When the key is empty no Authorization header is sent (for local or
key-free providers).

Lifecycle
---------
The adapter manages its own ``httpx.AsyncClient`` when none is injected.
Injected clients (for testing) are never closed by the adapter.

AIO/GEO Support
---------------
The base ``HttpSearchProvider`` does NOT support AIO extraction or GEO queries
because the generic contract does not define these endpoints.  Subclasses or
specialized providers (like ``SerpApiProvider``) should override
``supports_aio``, ``supports_geo``, ``extract_aio``, and ``query_geo``.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

import httpx

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_aio import AIOverviewObservation
from sie.domain.models.search_geo import GenerativeEngineType, GEOObservation
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

__all__ = ["HttpSearchProvider"]


class HttpSearchProvider:
    """HTTP implementation of the ``SearchProvider`` protocol.

    Parameters
    ----------
    base_url:
        Root URL of the search API (e.g. ``https://api.example.com``).
        Trailing slashes are stripped.
    api_key:
        Optional bearer token.  Empty string means no auth header is sent.
    timeout_seconds:
        Per-request timeout (legacy, used if granular timeouts not provided).
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
        When provided the adapter will **not** close it on ``close()``.
    allow_localhost:
        If True, allow connections to localhost/private IPs.
        ONLY enable for development/testing. Default: False.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 30.0,
        write_timeout_seconds: float = 10.0,
        pool_timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
        allow_localhost: bool = False,
    ) -> None:
        # Validate base_url against SSRF attacks
        safe, error = validate_url(base_url, allow_localhost=allow_localhost)
        if not safe:
            raise SearchProviderError(f"Invalid base_url (SSRF protection): {error}")

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._allow_localhost = allow_localhost

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Use granular timeouts for better control
        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )

        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
        )
        self._owns_client = client is None

    # ── SearchProvider protocol ──────────────────────────────────────────

    @property
    def supports_aio(self) -> bool:
        """Base HTTP provider does not support AIO (no standard contract)."""
        return False

    @property
    def supports_geo(self) -> bool:
        """Base HTTP provider does not support GEO (no standard contract)."""
        return False

    async def search(self, query: SearchQuery) -> SearchResult:
        """Execute a search query and return provider-neutral results.

        Raises a domain-specific error subclass on any failure.
        """
        url = f"{self._base_url}/search"
        payload = self._build_payload(query)

        logger.debug("Search request to %s query=%r", url, query.query)

        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            response = await self._client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning("Search request timed out: %s", exc)
            raise SearchProviderTimeout(f"Search request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.warning("Search request transport error: %s", exc)
            raise SearchProviderError(f"Search transport error: {exc}") from exc

        if response.status_code in (401, 403):
            raise SearchProviderAuthenticationError("Search API key is invalid or missing")
        if response.status_code == 429:
            raise SearchProviderRateLimit("Search rate limit exceeded")
        if response.status_code >= 400:
            body = response.text[:500]
            raise SearchProviderError(f"Search API returned HTTP {response.status_code}: {body}")

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise SearchProviderError(f"Search API returned invalid JSON: {exc}") from exc

        return self._parse_response(query, data)

    async def extract_aio(
        self, query: SearchQuery, target_domain: str
    ) -> AIOverviewObservation | None:
        """Base HTTP provider does not support AIO extraction.

        Returns None to indicate the capability is not available.
        Subclasses should override if the upstream API supports AIO.
        """
        return None

    async def query_geo(
        self, query: SearchQuery, target_domain: str, engine_type: GenerativeEngineType
    ) -> GEOObservation | None:
        """Base HTTP provider does not support GEO queries.

        Returns None to indicate the capability is not available.
        Subclasses should override if the upstream API supports GEO.
        """
        return None

    async def close(self) -> None:
        """Release the internally-created HTTP client (if any)."""
        if self._owns_client:
            await self._client.aclose()

    # ── internal helpers ─────────────────────────────────────────────────

    @staticmethod
    def _build_payload(query: SearchQuery) -> dict[str, object]:
        """Serialize a ``SearchQuery`` into the generic request JSON."""
        payload: dict[str, object] = {
            "query": query.query,
            "country": query.country,
            "language": query.language,
            "device": query.device.value,
            "search_engine": query.search_engine,
            "max_results": query.max_results,
        }
        if query.target_domain is not None:
            payload["target_domain"] = query.target_domain
        return payload

    @staticmethod
    def _parse_response(query: SearchQuery, data: object) -> SearchResult:
        """Validate and convert raw JSON into a ``SearchResult``.

        Never trusts the provider blindly — every field is validated.
        """
        if not isinstance(data, dict):
            raise SearchProviderError(
                f"Search API response is not a JSON object, got {type(data).__name__}"
            )

        raw_results = data.get("results")
        if raw_results is None:
            raise SearchProviderError("Search API response missing 'results' field")
        if not isinstance(raw_results, list):
            raise SearchProviderError(f"'results' must be a list, got {type(raw_results).__name__}")

        items: list[SearchResultItem] = []
        for idx, raw_item in enumerate(raw_results):
            if not isinstance(raw_item, dict):
                raise SearchProviderError(
                    f"Result item at index {idx} is not an object, got {type(raw_item).__name__}"
                )
            items.append(_parse_item(raw_item, idx))

        return SearchResult(
            keyword=query.query,
            search_engine=query.search_engine,
            country=query.country,
            language=query.language,
            device=query.device,
            items=tuple(items),
        )


def _parse_item(raw: dict[str, object], index: int) -> SearchResultItem:
    """Validate one result item dict and return a ``SearchResultItem``."""
    # -- title --
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SearchProviderError(f"Result item at index {index} has invalid 'title': {title!r}")

    # -- url --
    url = raw.get("url")
    if not isinstance(url, str) or not url.strip():
        raise SearchProviderError(f"Result item at index {index} has invalid 'url': {url!r}")
    parsed_url = urlparse(url.strip())
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise SearchProviderError(f"Result item at index {index} has invalid URL scheme: {url!r}")

    # -- position --
    position = raw.get("position")
    if isinstance(position, bool) or not isinstance(position, int):
        raise SearchProviderError(
            f"Result item at index {index} has invalid 'position': {position!r}"
        )
    if position < 1:
        raise SearchProviderError(
            f"Result item at index {index} has non-positive 'position': {position}"
        )

    return SearchResultItem(position=position, title=title.strip(), url=url.strip())
