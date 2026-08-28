"""Integration test for SiteAnalysis with multi-provider registry (Phase 1)."""

from __future__ import annotations

import pytest

from sie.domain.models.search_aio import (
    AIOverviewObservation,
    AIOverviewType,
)
from sie.domain.models.search_geo import (
    GenerativeEngineType,
    GEOObservation,
)
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.services.site_analysis import SiteAnalysisService
from sie.infrastructure.search.mock_provider import MockSearchProvider
from sie.infrastructure.search.provider_registry import ProviderRegistry


def _search_result_with_domain(domain: str, position: int = 1) -> SearchResult:
    """Create a SearchResult with a single item for the given domain."""
    return SearchResult(
        keyword="test keyword",
        items=(
            SearchResultItem(
                position=position,
                title="Test Page",
                url=f"https://{domain}/page",
            ),
        ),
    )


def _aio_observation_present(domain: str) -> AIOverviewObservation:
    """Create an AIOverviewObservation with AIO present and target cited."""
    return AIOverviewObservation(
        keyword="test keyword",
        ai_type=AIOverviewType.AI_OVERVIEW,
        present=True,
        target_cited=True,
        target_domain=domain,
        citation_count=1,
        citations=(),
        competitor_cited_domains=("competitor.com",),
    )


def _aio_observation_absent(domain: str) -> AIOverviewObservation:
    """Create an AIOverviewObservation with AIO not present."""
    return AIOverviewObservation(
        keyword="test keyword",
        ai_type=AIOverviewType.AI_OVERVIEW,
        present=False,
        target_cited=False,
        target_domain=domain,
        citation_count=0,
        citations=(),
        competitor_cited_domains=(),
    )


def _geo_observation_mentioned(domain: str) -> GEOObservation:
    """Create a GEOObservation with target mentioned."""
    return GEOObservation(
        keyword="test keyword",
        engine_type=GenerativeEngineType.CHATGPT,
        target_mentioned=True,
        target_domain=domain,
        mention_count=1,
        entity_mentions=(),
        competitor_domains=("competitor.com",),
        citation_urls=(),
        answer_length=100,
    )


def _geo_observation_not_mentioned(domain: str) -> GEOObservation:
    """Create a GEOObservation with target not mentioned."""
    return GEOObservation(
        keyword="test keyword",
        engine_type=GenerativeEngineType.CHATGPT,
        target_mentioned=False,
        target_domain=domain,
        mention_count=0,
        entity_mentions=(),
        competitor_domains=("competitor.com",),
        citation_urls=(),
        answer_length=100,
    )


class TestProviderRegistryRouting:
    """Tests for ProviderRegistry capability routing."""

    @pytest.fixture
    def serpapi_mock(self) -> MockSearchProvider:
        """Mock provider simulating SerpAPI with AIO support."""
        return MockSearchProvider(
            results={"test keyword": _search_result_with_domain("oursite.io")},
            aio_observations={
                "test keyword": _aio_observation_present("oursite.io"),
            },
        )

    @pytest.fixture
    def geo_mock(self) -> MockSearchProvider:
        """Mock provider simulating GEO LLM provider."""
        return MockSearchProvider(
            geo_observations={
                ("test keyword", GenerativeEngineType.CHATGPT): _geo_observation_mentioned(
                    "oursite.io"
                ),
            },
        )

    @pytest.fixture
    def rankings_mock(self) -> MockSearchProvider:
        """Mock provider for rankings only."""
        return MockSearchProvider(
            results={"test keyword": _search_result_with_domain("oursite.io")},
        )

    def test_explicit_rankings_provider(self, serpapi_mock, geo_mock, rankings_mock):
        """Test explicit rankings provider selection."""
        registry = ProviderRegistry(
            rankings=rankings_mock,
            aio=serpapi_mock,
            geo=geo_mock,
        )

        assert registry.get_for_rankings() is rankings_mock

    def test_fallback_to_default_for_rankings(self, rankings_mock):
        """Test fallback to default for rankings."""
        registry = ProviderRegistry(default=rankings_mock)

        assert registry.get_for_rankings() is rankings_mock

    def test_fallback_to_first_available_for_rankings(self, serpapi_mock, rankings_mock):
        """Test fallback to first available for rankings."""
        registry = ProviderRegistry(rankings=rankings_mock, aio=serpapi_mock)

        assert registry.get_for_rankings() is rankings_mock

    def test_no_rankings_provider_returns_none(self, serpapi_mock):
        """Test None when no rankings provider."""
        registry = ProviderRegistry(aio=serpapi_mock)

        assert registry.get_for_rankings() is None

    def test_explicit_aio_provider(self, serpapi_mock):
        """Test explicit AIO provider selection."""
        registry = ProviderRegistry(aio=serpapi_mock)

        assert registry.get_for_aio() is serpapi_mock

    def test_fallback_to_default_if_supports_aio(self):
        """Test fallback to default if it supports AIO."""
        from sie.domain.models.search_aio import AIOverviewObservation, AIOverviewType
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        mock = MockSearchProvider(
            aio_observations={
                "test": AIOverviewObservation(
                    keyword="test",
                    ai_type=AIOverviewType.AI_OVERVIEW,
                    present=True,
                    target_cited=True,
                    target_domain="example.com",
                ),
            },
        )
        registry = ProviderRegistry(default=mock)

        assert registry.get_for_aio() is mock

    def test_fallback_to_first_provider_with_aio(self, serpapi_mock, geo_mock):
        """Test fallback to first provider with AIO support."""
        registry = ProviderRegistry(aio=serpapi_mock, geo=geo_mock)

        assert registry.get_for_aio() is serpapi_mock

    def test_default_without_aio_returns_none(self):
        """Test default without AIO returns None."""
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        mock = MockSearchProvider()  # No AIO fixtures
        registry = ProviderRegistry(default=mock)

        assert registry.get_for_aio() is None

    def test_no_aio_capable_provider_returns_none(self, geo_mock):
        """Test None when no AIO-capable provider."""
        registry = ProviderRegistry(geo=geo_mock)

        assert registry.get_for_aio() is None

    def test_explicit_geo_provider(self, geo_mock):
        """Test explicit GEO provider selection."""
        registry = ProviderRegistry(geo=geo_mock)

        assert registry.get_for_geo() is geo_mock

    def test_fallback_to_default_if_supports_geo(self):
        """Test fallback to default if it supports GEO."""
        from sie.domain.models.search_geo import GenerativeEngineType, GEOObservation
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        mock = MockSearchProvider(
            geo_observations={
                ("test", GenerativeEngineType.CHATGPT): GEOObservation(
                    keyword="test",
                    engine_type=GenerativeEngineType.CHATGPT,
                    target_mentioned=True,
                    target_domain="example.com",
                ),
            },
        )
        registry = ProviderRegistry(default=mock)

        assert registry.get_for_geo() is mock

    def test_fallback_to_first_provider_with_geo(self, serpapi_mock, geo_mock):
        """Test fallback to first provider with GEO support."""
        registry = ProviderRegistry(aio=serpapi_mock, geo=geo_mock)

        assert registry.get_for_geo() is geo_mock

    def test_default_without_geo_returns_none(self):
        """Test default without GEO returns None."""
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        mock = MockSearchProvider()  # No GEO fixtures
        registry = ProviderRegistry(default=mock)

        assert registry.get_for_geo() is None

    def test_no_geo_capable_provider_returns_none(self, serpapi_mock):
        """Test None when no GEO-capable provider."""
        registry = ProviderRegistry(aio=serpapi_mock)

        assert registry.get_for_geo() is None

    def test_single_provider_as_default(self):
        """Test single provider as default works for all capabilities."""
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        mock = MockSearchProvider(
            results={
                "test": SearchResult(
                    keyword="test",
                    items=(
                        SearchResultItem(position=1, title="Test", url="https://example.com/page"),
                    ),
                )
            },
            aio_observations={
                "test": AIOverviewObservation(
                    keyword="test",
                    ai_type=AIOverviewType.AI_OVERVIEW,
                    present=True,
                    target_cited=True,
                    target_domain="example.com",
                ),
            },
            geo_observations={
                ("test", GenerativeEngineType.CHATGPT): GEOObservation(
                    keyword="test",
                    engine_type=GenerativeEngineType.CHATGPT,
                    target_mentioned=True,
                    target_domain="example.com",
                ),
            },
        )

        registry = ProviderRegistry(default=mock)

        assert registry.get_for_rankings() is mock
        assert registry.get_for_aio() is mock
        assert registry.get_for_geo() is mock

    def test_single_provider_without_capabilities(self):
        """Test single provider without AIO/GEO capabilities."""
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        mock = MockSearchProvider()
        registry = ProviderRegistry(default=mock)

        assert registry.get_for_rankings() is mock
        assert registry.get_for_aio() is None
        assert registry.get_for_geo() is None

    def test_same_provider_for_multiple_capabilities(self, serpapi_mock):
        """Test same provider registered for multiple capabilities."""
        registry = ProviderRegistry(rankings=serpapi_mock, aio=serpapi_mock)

        assert registry.get_for_rankings() is serpapi_mock
        assert registry.get_for_aio() is serpapi_mock
        assert registry.get_for_geo() is None

    def test_all_return_none(self):
        """Test all return None when no providers registered."""
        registry = ProviderRegistry()

        assert registry.get_for_rankings() is None
        assert registry.get_for_aio() is None
        assert registry.get_for_geo() is None

    def test_mock_provider_with_aio_fixture(self):
        """Test mock provider with AIO fixture."""
        from sie.domain.models.search_aio import AIOverviewObservation, AIOverviewType

        aio_obs = AIOverviewObservation(
            keyword="test",
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=True,
            target_domain="example.com",
        )
        mock = MockSearchProvider(aio_observations={"test": aio_obs})

        registry = ProviderRegistry(aio=mock)

        assert registry.get_for_aio() is mock

    def test_mock_provider_with_geo_fixture(self):
        """Test mock provider with GEO fixture."""
        from sie.domain.models.search_geo import GenerativeEngineType, GEOObservation

        geo_obs = GEOObservation(
            keyword="test",
            engine_type=GenerativeEngineType.CHATGPT,
            target_mentioned=True,
            target_domain="example.com",
        )
        mock = MockSearchProvider(
            geo_observations={("test", GenerativeEngineType.CHATGPT): geo_obs}
        )

        registry = ProviderRegistry(geo=mock)

        assert registry.get_for_geo() is mock


class TestSiteAnalysisMultiProvider:
    """Integration tests for SiteAnalysisService with multi-provider registry."""

    @pytest.fixture
    def serpapi_mock(self) -> MockSearchProvider:
        """Mock provider simulating SerpAPI with AIO support."""
        return MockSearchProvider(
            results={"test keyword": _search_result_with_domain("oursite.io")},
            aio_observations={
                "test keyword": AIOverviewObservation(
                    keyword="test keyword",
                    ai_type=AIOverviewType.AI_OVERVIEW,
                    present=True,
                    target_cited=True,
                    target_domain="oursite.io",
                    citation_count=1,
                    citations=(),
                    competitor_cited_domains=("competitor.com",),
                ),
            },
        )

    @pytest.fixture
    def geo_mock(self) -> MockSearchProvider:
        """Mock provider simulating GEO LLM provider."""
        return MockSearchProvider(
            geo_observations={
                ("test keyword", GenerativeEngineType.CHATGPT): GEOObservation(
                    keyword="test keyword",
                    engine_type=GenerativeEngineType.CHATGPT,
                    target_mentioned=True,
                    target_domain="oursite.io",
                    mention_count=1,
                    entity_mentions=(),
                    competitor_domains=("competitor.com",),
                    citation_urls=(),
                    answer_length=100,
                ),
            },
        )

    @pytest.fixture
    def rankings_mock(self) -> MockSearchProvider:
        """Mock provider for rankings only."""
        return MockSearchProvider(
            results={"test keyword": _search_result_with_domain("oursite.io")},
        )

    @pytest.mark.asyncio
    async def test_site_analysis_with_separate_aio_and_geo_providers(
        self,
        serpapi_mock: MockSearchProvider,
        geo_mock: MockSearchProvider,
        rankings_mock: MockSearchProvider,
    ):
        """Test SiteAnalysis with separate providers for AIO and GEO."""
        # Create registry with separate providers
        registry = ProviderRegistry(
            rankings=rankings_mock,
            aio=serpapi_mock,
            geo=geo_mock,
        )

        # Verify routing
        assert registry.get_for_rankings() is rankings_mock
        assert registry.get_for_aio() is serpapi_mock
        assert registry.get_for_geo() is geo_mock

        # Create service with registry
        from unittest.mock import AsyncMock, MagicMock

        from sie.domain.ports.persistence import CrawlRunRepository
        from sie.domain.services.audit_service import AuditService
        from sie.domain.services.content_service import ContentService
        from sie.domain.services.crawl_service import CrawlService

        crawl_service = MagicMock(spec=CrawlService)
        audit_service = MagicMock(spec=AuditService)
        content_service = MagicMock(spec=ContentService)
        repository = MagicMock(spec=CrawlRunRepository)

        # Setup mocks
        crawl_service.start_run = AsyncMock(return_value="run-123")
        crawl_service.live_stats = AsyncMock(
            return_value=MagicMock(status=MagicMock(value="completed"))
        )
        crawl_service._pages_store = {"run-123": []}

        audit_service.run_technical_audit = AsyncMock(
            return_value=MagicMock(
                critical_count=0,
                warning_count=0,
                info_count=0,
                findings=[],
                summary_by_rule={},
            )
        )
        audit_service.run_link_graph = AsyncMock(
            return_value=MagicMock(
                total_pages=0,
                total_internal_links=0,
                avg_depth=0,
                orphans=[],
                max_depth=0,
                pagerank_gini=0.0,
                avg_links_per_page=0,
            )
        )

        content_service.analyze_content = AsyncMock(return_value=[])
        content_service.generate_quality_report = AsyncMock(
            return_value=MagicMock(
                analyzed_pages=0,
                avg_quality_score=0.0,
                thin_content_pages=0,
                duplicate_groups=0,
                top_issues=[],
            )
        )

        repository.get_search_dataset = AsyncMock(return_value=None)
        repository.save_search_observations = AsyncMock(return_value=0)

        service = SiteAnalysisService(
            crawl_service=crawl_service,
            audit_service=audit_service,
            content_service=content_service,
            search_provider=registry,
            repository=repository,
        )

        # Run analysis with minimal setup
        result = await service.analyze_site(
            domain="oursite.io",
            max_pages=1,
            max_keywords=1,
            deep_aio=True,
            deep_geo=True,
        )

        # Verify the analysis ran without errors
        assert result.domain == "oursite.io"
        # Note: Actual AIO/GEO results will be empty because crawl returns no pages
        # but the registry routing should work without errors

    @pytest.mark.asyncio
    async def test_registry_routing_with_serpapi_for_aio_and_rankings(
        self,
        serpapi_mock: MockSearchProvider,
    ):
        """Test registry where SerpAPI handles both rankings and AIO."""
        registry = ProviderRegistry(
            rankings=serpapi_mock,
            aio=serpapi_mock,
        )

        assert registry.get_for_rankings() is serpapi_mock
        assert registry.get_for_aio() is serpapi_mock
        assert registry.get_for_geo() is None

    @pytest.mark.asyncio
    async def test_single_provider_backward_compatibility(self):
        """Test that a single provider still works for all capabilities."""
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        # Single provider that supports everything
        mock = MockSearchProvider(
            results={
                "test": SearchResult(
                    keyword="test",
                    items=(
                        SearchResultItem(position=1, title="Test", url="https://example.com/page"),
                    ),
                )
            },
            aio_observations={
                "test": AIOverviewObservation(
                    keyword="test",
                    ai_type=AIOverviewType.AI_OVERVIEW,
                    present=True,
                    target_cited=True,
                    target_domain="example.com",
                ),
            },
            geo_observations={
                ("test", GenerativeEngineType.CHATGPT): GEOObservation(
                    keyword="test",
                    engine_type=GenerativeEngineType.CHATGPT,
                    target_mentioned=True,
                    target_domain="example.com",
                ),
            },
        )

        registry = ProviderRegistry(default=mock)

        assert registry.get_for_rankings() is mock
        assert registry.get_for_aio() is mock
        assert registry.get_for_geo() is mock


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
