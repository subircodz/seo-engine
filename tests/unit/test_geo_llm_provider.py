"""Unit tests for GEO LLM Provider (Phase 6N-G + GEO real data).

Tests the GEOLLMProvider's ability to query LLMs and extract
brand/entity mentions from responses using mocked HTTP transport.
"""

from __future__ import annotations

import httpx
import pytest

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_geo import (
    EntityType,
    GenerativeEngineType,
    GEOObservation,
)
from sie.domain.ports.llm import LLMProviderError
from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider
from sie.infrastructure.search.geo_provider import GEOLLMProvider


def _mock_llm_response(
    status_code: int = 200,
    content: str = "Test response mentioning OurSite and Competitor.com",
    json_data: object = None,
) -> httpx.Response:
    """Build a minimal httpx.Response without network."""
    import json

    if json_data is not None:
        content_bytes = json.dumps(json_data).encode()
    else:
        # Wrap content in the expected OpenAI response format
        response_obj = {"choices": [{"message": {"content": content}}]}
        content_bytes = json.dumps(response_obj).encode()
    return httpx.Response(
        status_code=status_code,
        content=content_bytes,
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )


def _llm_provider(
    response_content: str = "Test response mentioning OurSite and Competitor.com",
    status_code: int = 200,
    *,
    base_url: str = "https://api.openai.com",
    api_key: str = "test-key",
    model: str = "gpt-4o-mini",
    json_data: object = None,
) -> OpenAICompatibleProvider:
    """Create an OpenAICompatibleProvider with a mocked transport."""
    if json_data is not None:
        response = _mock_llm_response(status_code=status_code, json_data=json_data)
    else:
        response = _mock_llm_response(status_code=status_code, content=response_content)

    def _handler(request: httpx.Request) -> httpx.Response:
        return response

    transport = httpx.MockTransport(_handler)
    client = httpx.AsyncClient(transport=transport)
    return OpenAICompatibleProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        client=client,
    )


def _geo_provider(
    llm_provider: OpenAICompatibleProvider | None = None,
    target_brand_names: list[str] | None = None,
    competitor_domains: list[str] | None = None,
) -> GEOLLMProvider:
    """Create a GEOLLMProvider with optional custom LLM provider."""
    llm = llm_provider or _llm_provider()
    return GEOLLMProvider(
        llm_provider=llm,
        target_brand_names=target_brand_names or ["oursite", "our site"],
        competitor_domains=competitor_domains or ["competitor.com", "other.com"],
    )


def _query(**overrides) -> SearchQuery:
    defaults = {"query": "best seo tools", "target_domain": "oursite.io"}
    defaults.update(overrides)
    return SearchQuery(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# GEOLLMProvider capability properties
# ═════════════════════════════════════════════════════════════════════════════


class TestGEOLLMProviderCapabilities:
    def test_supports_geo_is_true(self):
        provider = _geo_provider()
        assert provider.supports_geo is True

    def test_supports_aio_is_false(self):
        provider = _geo_provider()
        assert provider.supports_aio is False


# ═════════════════════════════════════════════════════════════════════════════
# query_geo — target brand mentioned
# ═════════════════════════════════════════════════════════════════════════════


class TestQueryGEOTargetMentioned:
    async def test_target_mentioned_once(self):
        llm = _llm_provider(
            response_content=(
                "For SEO tools, I recommend OurSite as the best option. "
                "It has great features."
            )
        )
        provider = _geo_provider(llm_provider=llm, target_brand_names=["oursite"])
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        assert obs is not None
        assert isinstance(obs, GEOObservation)
        assert obs.keyword == "best seo tools"
        assert obs.engine_type == GenerativeEngineType.CHATGPT
        assert obs.target_mentioned is True
        assert obs.target_domain == "oursite.io"
        assert obs.mention_count >= 1
        assert obs.source == "llm-chatgpt"

    async def test_target_mentioned_multiple_times(self):
        llm = _llm_provider(
            response_content=(
                "OurSite is great. OurSite has many features. "
                "I highly recommend OurSite."
            )
        )
        provider = _geo_provider(llm_provider=llm, target_brand_names=["oursite"])
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        assert obs.target_mentioned is True
        assert obs.mention_count == 3

    async def test_target_mentioned_case_insensitive(self):
        llm = _llm_provider(response_content="OURSITE is the best. our site is also good.")
        provider = _geo_provider(llm_provider=llm, target_brand_names=["oursite", "our site"])
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        assert obs.target_mentioned is True
        assert obs.mention_count >= 2


# ═════════════════════════════════════════════════════════════════════════════
# query_geo — competitor mentioned
# ═════════════════════════════════════════════════════════════════════════════


class TestQueryGEOCompetitorMentioned:
    async def test_competitor_domain_mentioned(self):
        llm = _llm_provider(
            response_content=(
                "Competitor.com offers a good alternative. "
                "Their pricing is competitive."
            )
        )
        provider = _geo_provider(llm_provider=llm, competitor_domains=["competitor.com"])
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        assert "competitor.com" in obs.competitor_domains

    async def test_multiple_competitors_mentioned(self):
        llm = _llm_provider(response_content="Competitor.com and Other.com are both good options.")
        provider = _geo_provider(
            llm_provider=llm, competitor_domains=["competitor.com", "other.com"]
        )
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        assert "competitor.com" in obs.competitor_domains
        assert "other.com" in obs.competitor_domains

    async def test_citation_urls_extracted(self):
        llm = _llm_provider(
            response_content=(
                "Check out https://competitor.com/tools and "
                "https://example.com/review for more info."
            )
        )
        provider = _geo_provider(llm_provider=llm)
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        assert len(obs.citation_urls) >= 2
        assert any("competitor.com" in url for url in obs.citation_urls)
        assert any("example.com" in url for url in obs.citation_urls)


# ═════════════════════════════════════════════════════════════════════════════
# query_geo — target NOT mentioned
# ═════════════════════════════════════════════════════════════════════════════


class TestQueryGEOTargetNotMentioned:
    async def test_target_not_mentioned(self):
        llm = _llm_provider(
            response_content=(
                "There are many SEO tools available. "
                "Competitor.com is a popular choice."
            )
        )
        provider = _geo_provider(llm_provider=llm, target_brand_names=["oursite"])
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        assert obs.target_mentioned is False
        assert obs.mention_count == 0
        assert obs.target_domain == "oursite.io"


# ═════════════════════════════════════════════════════════════════════════════
# query_geo — entity mentions structure
# ═════════════════════════════════════════════════════════════════════════════


class TestQueryGEOEntityMentions:
    async def test_entity_mentions_include_target(self):
        llm = _llm_provider(response_content="OurSite is recommended for SEO.")
        provider = _geo_provider(llm_provider=llm, target_brand_names=["oursite"])
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        target_mentions = [m for m in obs.entity_mentions if m.is_target]
        assert len(target_mentions) >= 1
        assert target_mentions[0].entity_type == EntityType.BRAND
        assert target_mentions[0].domain == "oursite.io"

    async def test_entity_mentions_include_competitors(self):
        llm = _llm_provider(response_content="Competitor.com is a good alternative.")
        provider = _geo_provider(llm_provider=llm, competitor_domains=["competitor.com"])
        query = _query(query="best seo tools")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)

        comp_mentions = [m for m in obs.entity_mentions if not m.is_target]
        assert len(comp_mentions) >= 1
        assert comp_mentions[0].entity_type == EntityType.BRAND
        assert comp_mentions[0].domain == "competitor.com"


# ═════════════════════════════════════════════════════════════════════════════
# query_geo — error handling
# ═════════════════════════════════════════════════════════════════════════════


class TestQueryGEOErrors:
    async def test_llm_timeout_raises(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("connection timed out")

        transport = httpx.MockTransport(_handler)
        client = httpx.AsyncClient(transport=transport)
        llm = OpenAICompatibleProvider(base_url="https://api.openai.com", client=client)
        provider = _geo_provider(llm_provider=llm)
        query = _query()

        with pytest.raises(Exception) as exc_info:
            await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)
        assert "timed out" in str(exc_info.value).lower()

    async def test_llm_401_raises_auth_error(self):
        llm = _llm_provider(status_code=401, json_data={"error": "Unauthorized"})
        provider = _geo_provider(llm_provider=llm)
        query = _query()

        with pytest.raises(Exception) as exc_info:
            await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)
        assert "invalid or missing" in str(exc_info.value).lower()

    async def test_malformed_llm_response_raises(self):
        llm = _llm_provider(status_code=200, json_data={"invalid": "structure"})
        provider = _geo_provider(llm_provider=llm)
        query = _query()

        with pytest.raises(LLMProviderError):
            await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)


# ═════════════════════════════════════════════════════════════════════════════
# query_geo — different engine types
# ═════════════════════════════════════════════════════════════════════════════


class TestQueryGEOEngineTypes:
    async def test_chatgpt_engine_type(self):
        llm = _llm_provider(response_content="Test response")
        provider = _geo_provider(llm_provider=llm)
        query = _query(query="test")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CHATGPT)
        assert obs.engine_type == GenerativeEngineType.CHATGPT

    async def test_perplexity_engine_type(self):
        llm = _llm_provider(response_content="Test response with citations https://source.com")
        provider = _geo_provider(llm_provider=llm)
        query = _query(query="test")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.PERPLEXITY)
        assert obs.engine_type == GenerativeEngineType.PERPLEXITY

    async def test_claude_engine_type(self):
        llm = _llm_provider(response_content="Test response")
        provider = _geo_provider(llm_provider=llm)
        query = _query(query="test")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.CLAUDE)
        assert obs.engine_type == GenerativeEngineType.CLAUDE

    async def test_gemini_engine_type(self):
        llm = _llm_provider(response_content="Test response")
        provider = _geo_provider(llm_provider=llm)
        query = _query(query="test")
        obs = await provider.query_geo(query, "oursite.io", GenerativeEngineType.GEMINI)
        assert obs.engine_type == GenerativeEngineType.GEMINI
