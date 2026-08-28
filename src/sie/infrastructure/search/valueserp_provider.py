"""ValueSERP search provider with AIO extraction support.

Implements the ``SearchProvider`` protocol for ValueSERP's GET-based API.
Supports AI Overview (AIO) extraction via the ``include_ai_overview`` parameter.
"""

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
from sie.logging import get_logger

logger = get_logger(__name__)

__all__ = ["ValueSerpProvider"]


class ValueSerpProvider:
    """ValueSERP implementation of the ``SearchProvider`` protocol.

    Parameters
    ----------
    api_key:
        ValueSERP API key.
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
            raise SearchProviderError("ValueSERP requires an API key")

        self._api_key = api_key
        self._base_url = "https://api.valueserp.com/search"

        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )

        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    @property
    def supports_aio(self) -> bool:
        """ValueSERP supports AI Overview extraction via the include_ai_overview parameter."""
        return True

    @property
    def supports_geo(self) -> bool:
        """ValueSERP does not directly support generative engine queries."""
        return False

    async def search(self, query: SearchQuery) -> SearchResult:
        """Execute a search query via ValueSERP and return provider-neutral results."""
        params = self._build_params(query)

        logger.debug("ValueSERP request query=%r", query.query)

        try:
            response = await self._client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("ValueSERP request timed out: %s", exc)
            raise SearchProviderTimeout(f"Search request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.warning("ValueSERP request transport error: %s", exc)
            raise SearchProviderError(f"Search transport error: {exc}") from exc

        if response.status_code in (401, 403):
            raise SearchProviderAuthenticationError("ValueSERP key is invalid or missing")
        if response.status_code == 429:
            raise SearchProviderRateLimit("ValueSERP rate limit exceeded")
        if response.status_code >= 400:
            body = response.text[:500]
            raise SearchProviderError(f"ValueSERP returned HTTP {response.status_code}: {body}")

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise SearchProviderError(f"ValueSERP returned invalid JSON: {exc}") from exc

        return self._parse_response(query, data)

    async def extract_aio(
        self, query: SearchQuery, target_domain: str
    ) -> AIOverviewObservation | None:
        """Extract AI Overview observation from ValueSERP response.

        ValueSERP returns AI Overview data in the 'ai_overview' field when
        ``include_ai_overview=true`` is passed.
        Returns None if the provider cannot extract AIO data.
        """
        params = self._build_params(query)
        # Always request AI Overview data
        params["include_ai_overview"] = "true"

        try:
            response = await self._client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("ValueSERP AIO request timed out: %s", exc)
            raise SearchProviderTimeout(f"Search request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.warning("ValueSERP AIO request transport error: %s", exc)
            raise SearchProviderError(f"Search transport error: {exc}") from exc

        if response.status_code in (401, 403):
            raise SearchProviderAuthenticationError("ValueSERP key is invalid or missing")
        if response.status_code == 429:
            raise SearchProviderRateLimit("ValueSERP rate limit exceeded")
        if response.status_code >= 400:
            body = response.text[:500]
            raise SearchProviderError(f"ValueSERP returned HTTP {response.status_code}: {body}")

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise SearchProviderError(f"ValueSERP returned invalid JSON: {exc}") from exc

        return self._parse_aio_response(query.query, target_domain, data)

    async def query_geo(
        self, query: SearchQuery, target_domain: str, engine_type: GenerativeEngineType
    ) -> GEOObservation | None:
        """ValueSERP does not support generative engine queries.

        Raises SearchProviderCapabilityError since this provider cannot
        perform GEO observations.
        """
        raise SearchProviderCapabilityError(
            f"ValueSerpProvider does not support GEO queries for engine {engine_type.value}"
        )

    async def close(self) -> None:
        """Release the internally-created HTTP client (if any)."""
        if self._owns_client:
            await self._client.aclose()

    def _build_params(self, query: SearchQuery) -> dict[str, str]:
        """Serialize a ``SearchQuery`` into ValueSERP query parameters."""
        params = {
            "q": query.query,
            "gl": query.country,
            "hl": query.language,
            "device": query.device.value,
            "engine": "google",
            "num": str(query.max_results),
            "api_key": self._api_key,
        }
        return params

    def _parse_response(self, query: SearchQuery, data: object) -> SearchResult:
        """Validate and convert ValueSERP JSON into a ``SearchResult``."""
        if not isinstance(data, dict):
            raise SearchProviderError(
                f"ValueSERP response is not a JSON object, got {type(data).__name__}"
            )

        organic_results = data.get("organic_results")
        if organic_results is None:
            raise SearchProviderError("ValueSERP response missing 'organic_results' field")
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
        """Parse AI Overview data from ValueSERP response.

        ValueSERP returns AI Overview data in the 'ai_overview' field when
        ``include_ai_overview=true`` is passed. The structure includes:
        - ai_overview_banner: string
        - ai_overview_contents: list of content objects
        - ai_overview_sources: list of source objects with title, url, etc.
        - ai_overview_footer: string
        """
        ai_overview = data.get("ai_overview")

        if not ai_overview or not isinstance(ai_overview, dict):
            # No AI Overview present
            return AIOverviewObservation(
                keyword=keyword,
                ai_type=AIOverviewType.AI_OVERVIEW,
                present=False,
                target_cited=False,
                target_domain=target_domain,
                citation_count=0,
                citations=(),
                competitor_cited_domains=(),
                source="valueserp",
            )

        # AI Overview is present - extract sources
        citations = []
        competitor_domains = set()
        target_cited = False

        # ValueSERP ai_overview structure contains:
        # - ai_overview_sources: list of source objects with:
        #   - source_title: title of the source
        #   - source_description: description
        #   - source_url: URL of the source
        #   - source_image: base64 encoded image
        #   - source_name: name of the source
        raw_sources = ai_overview.get("ai_overview_sources")
        if isinstance(raw_sources, list):
            for idx, source in enumerate(raw_sources):
                if not isinstance(source, dict):
                    continue
                cite_url = source.get("source_url")
                cite_title = source.get("source_title") or source.get("source_name") or ""
                if not cite_url or not isinstance(cite_url, str):
                    continue
                parsed = urlparse(cite_url)
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    continue
                domain = parsed.netloc.split(":")[0].casefold()
                if domain.startswith("www."):
                    domain = domain[4:]

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

        citation_count = len(citations)

        return AIOverviewObservation(
            keyword=keyword,
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=True,
            target_cited=target_cited,
            target_domain=target_domain,
            citation_count=citation_count,
            citations=tuple(citations),
            competitor_cited_domains=tuple(sorted(competitor_domains)),
            source="valueserp",
        )

    @staticmethod
    def _parse_item(raw: dict[str, object], index: int) -> SearchResultItem | None:
        """Validate one ValueSERP organic result and return a ``SearchResultItem``."""
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
