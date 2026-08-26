"""Unit tests for SerpAPI AIO extraction (Phase 6N-F + AIO real data).

Tests the SerpApiProvider's ability to extract AI Overview observations
from SerpAPI responses using mocked HTTP transport.
"""

from __future__ import annotations

import httpx
import pytest

from sie.domain.models.search import SearchDevice, SearchQuery
from sie.domain.models.search_aio import (
    AIOverviewObservation,
    AIOverviewType,
    CitationSource,
)
from sie.domain.ports.search_provider import (
    SearchProviderAuthenticationError,
    SearchProviderRateLimit,
    SearchProviderTimeout,
)
from sie.infrastructure.search.serpapi_provider import SerpApiProvider


def _mock_serpapi_response(
    status_code: int = 200,
    json_data: object = None,
    text: str = "",
) -> httpx.Response:
    """Build a minimal httpx.Response without network."""
    import json
    content = json.dumps(json_data).encode() if json_data is not None else text.encode()
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://serpapi.com/search"),
    )


def _serpapi_provider(
    status_code: int = 200,
    json_data: object = None,
    *,
    text: str = "",
    api_key: str = "test-key",
) -> SerpApiProvider:
    """Create a SerpApiProvider with a mocked transport."""
    response = _mock_serpapi_response(status_code=status_code, json_data=json_data, text=text)

    def _handler(request: httpx.Request) -> httpx.Response:
        return response

    transport = httpx.MockTransport(_handler)
    client = httpx.AsyncClient(transport=transport)
    return SerpApiProvider(
        api_key=api_key,
        timeout_seconds=5.0,
        client=client,
    )


def _query(**overrides) -> SearchQuery:
    defaults = {"query": "best seo tools", "target_domain": "oursite.io"}
    defaults.update(overrides)
    return SearchQuery(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# SerpApiProvider capability properties
# ═════════════════════════════════════════════════════════════════════════════


class TestSerpApiProviderCapabilities:
    async def test_supports_aio_is_true(self):
        provider = _serpapi_provider(json_data={"organic_results": [], "ai_overview": None})
        assert provider.supports_aio is True

    async def test_supports_geo_is_false(self):
        provider = _serpapi_provider(json_data={"organic_results": []})
        assert provider.supports_geo is False


# ═════════════════════════════════════════════════════════════════════════════
# extract_aio — no AI Overview present
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractAIONoOverview:
    async def test_returns_observation_with_present_false(self):
        provider = _serpapi_provider(json_data={"organic_results": [], "ai_overview": None})
        query = _query(query="test query")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs is not None
        assert isinstance(obs, AIOverviewObservation)
        assert obs.keyword == "test query"
        assert obs.present is False
        assert obs.target_cited is False
        assert obs.citation_count == 0
        assert obs.citations == ()
        assert obs.competitor_cited_domains == ()
        assert obs.ai_type == AIOverviewType.AI_OVERVIEW
        assert obs.source == "serpapi"

    async def test_returns_observation_when_ai_overview_missing(self):
        provider = _serpapi_provider(json_data={"organic_results": []})
        query = _query(query="test query")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs is not None
        assert obs.present is False


# ═════════════════════════════════════════════════════════════════════════════
# extract_aio — AI Overview present with citations
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractAIOWithCitations:
    async def test_target_cited(self):
        provider = _serpapi_provider(json_data={
            "organic_results": [],
            "ai_overview": {
                "citations": [
                    {"title": "Our Site", "link": "https://oursite.io/best-seo-tools"},
                    {"title": "Competitor", "link": "https://competitor.com/seo-tools"},
                ]
            }
        })
        query = _query(query="best seo tools")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs.present is True
        assert obs.target_cited is True
        assert obs.citation_count == 2
        assert len(obs.citations) == 2
        assert obs.citations[0].domain == "oursite.io"
        assert obs.citations[0].url == "https://oursite.io/best-seo-tools"
        assert obs.citations[0].source_type == CitationSource.WEB_PAGE
        assert obs.citations[1].domain == "competitor.com"
        assert "competitor.com" in obs.competitor_cited_domains

    async def test_competitor_cited_not_target(self):
        provider = _serpapi_provider(json_data={
            "organic_results": [],
            "ai_overview": {
                "citations": [
                    {"title": "Competitor 1", "link": "https://competitor1.com/seo-tools"},
                    {"title": "Competitor 2", "link": "https://competitor2.com/seo-tools"},
                ]
            }
        })
        query = _query(query="best seo tools")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs.present is True
        assert obs.target_cited is False
        assert obs.citation_count == 2
        assert set(obs.competitor_cited_domains) == {"competitor1.com", "competitor2.com"}

    async def test_multiple_citations_same_domain(self):
        provider = _serpapi_provider(json_data={
            "organic_results": [],
            "ai_overview": {
                "citations": [
                    {"title": "Page 1", "link": "https://competitor.com/page1"},
                    {"title": "Page 2", "link": "https://competitor.com/page2"},
                ]
            }
        })
        query = _query(query="best seo tools")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs.citation_count == 2
        assert obs.competitor_cited_domains == ("competitor.com",)

    async def test_citation_position_ordered(self):
        provider = _serpapi_provider(json_data={
            "organic_results": [],
            "ai_overview": {
                "citations": [
                    {"title": "First", "link": "https://first.com"},
                    {"title": "Second", "link": "https://second.com"},
                    {"title": "Third", "link": "https://third.com"},
                ]
            }
        })
        query = _query(query="test")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs.citations[0].position == 0
        assert obs.citations[1].position == 1
        assert obs.citations[2].position == 2


# ═════════════════════════════════════════════════════════════════════════════
# extract_aio — malformed citation handling
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractAIOMalformedCitations:
    async def test_skips_citation_without_link(self):
        provider = _serpapi_provider(json_data={
            "organic_results": [],
            "ai_overview": {
                "citations": [
                    {"title": "No Link"},
                    {"title": "With Link", "link": "https://valid.com"},
                ]
            }
        })
        query = _query(query="test")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs.citation_count == 1
        assert obs.citations[0].domain == "valid.com"

    async def test_skips_citation_with_invalid_url(self):
        provider = _serpapi_provider(json_data={
            "organic_results": [],
            "ai_overview": {
                "citations": [
                    {"title": "Invalid", "link": "not-a-url"},
                    {"title": "Valid", "link": "https://valid.com"},
                ]
            }
        })
        query = _query(query="test")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs.citation_count == 1
        assert obs.citations[0].domain == "valid.com"

    async def test_skips_non_dict_citation(self):
        provider = _serpapi_provider(json_data={
            "organic_results": [],
            "ai_overview": {
                "citations": [
                    "not a dict",
                    {"title": "Valid", "link": "https://valid.com"},
                ]
            }
        })
        query = _query(query="test")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs.citation_count == 1

    async def test_empty_citations_list(self):
        provider = _serpapi_provider(json_data={
            "organic_results": [],
            "ai_overview": {"citations": []}
        })
        query = _query(query="test")
        obs = await provider.extract_aio(query, "oursite.io")

        assert obs.present is True
        assert obs.citation_count == 0
        assert obs.citations == ()


# ═════════════════════════════════════════════════════════════════════════════
# extract_aio — error handling
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractAIOErrors:
    async def test_401_raises_auth_error(self):
        provider = _serpapi_provider(status_code=401)
        query = _query()
        with pytest.raises(SearchProviderAuthenticationError):
            await provider.extract_aio(query, "oursite.io")

    async def test_429_raises_rate_limit(self):
        provider = _serpapi_provider(status_code=429)
        query = _query()
        with pytest.raises(SearchProviderRateLimit):
            await provider.extract_aio(query, "oursite.io")

    async def test_500_raises_provider_error(self):
        provider = _serpapi_provider(status_code=500, text="Internal Server Error")
        query = _query()
        with pytest.raises(Exception) as exc_info:
            await provider.extract_aio(query, "oursite.io")
        assert "HTTP 500" in str(exc_info.value)

    async def test_timeout_raises_timeout_error(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("connection timed out")

        transport = httpx.MockTransport(_handler)
        client = httpx.AsyncClient(transport=transport)
        provider = SerpApiProvider(api_key="test-key", client=client)
        query = _query()

        with pytest.raises(SearchProviderTimeout):
            await provider.extract_aio(query, "oursite.io")


# ═════════════════════════════════════════════════════════════════════════════
# query_geo — capability error
# ═════════════════════════════════════════════════════════════════════════════


class TestSerpApiProviderGEO:
    async def test_query_geo_raises_capability_error(self):
        provider = _serpapi_provider(json_data={"organic_results": []})
        query = _query()
        from sie.domain.models.search_geo import GenerativeEngineType
        from sie.domain.ports.search_provider import SearchProviderCapabilityError

        with pytest.raises(SearchProviderCapabilityError):
            await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)