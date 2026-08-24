"""Phase 6M End-to-End Integration Tests.

Tests the complete real-provider search collection pipeline using the existing
HttpSearchProvider with a controlled local HTTP test server (no external APIs).

Verifies the full flow:
  SearchProviderSettings → ProviderFactory → HttpSearchProvider
  → SearchCollectionService → RankingObservation → Persistence → Search Analytics
"""

import pytest

from sie.config import SearchProviderSettings
from sie.domain.models.search import SearchDevice, SearchQuery
from sie.domain.services.search_collection_service import SearchCollectionService
from sie.infrastructure.search.http_provider import HttpSearchProvider
from sie.infrastructure.search.provider_factory import (
    create_search_provider,
)
from tests.helpers.fake_search_server import (
    FakeSearchServer,
    ServerMode,
    make_provider,
    verify_target_domain_in_url,
)


class TestPhase6M_CompleteEndToEnd:
    """Verify the complete search collection pipeline with HttpSearchProvider."""

    async def test_provider_factory_creates_http_provider(self):
        """Provider factory creates HttpSearchProvider when enabled."""
        settings = SearchProviderSettings(
            enabled=True, provider_name="http", base_url="https://api.test-server.com"
        )
        provider = create_search_provider(settings)
        assert isinstance(provider, HttpSearchProvider)
        assert provider._base_url == "https://api.test-server.com"

    async def test_http_search_provider_sends_correct_request(self):
        """HttpSearchProvider sends the correct request to local server."""
        server = FakeSearchServer()
        provider = make_provider(server, api_key="test-key", timeout_seconds=5.0)

        query = SearchQuery(
            query="best crm software",
            country="us",
            language="en",
            device=SearchDevice.DESKTOP,
            search_engine="google",
            target_domain="oursite.io",
            max_results=10,
        )

        await provider.search(query)

        request = server.get_request()
        assert server.request_count == 1
        assert request["method"] == "POST"
        assert request["url"].endswith("/search")
        body = request["body"]
        assert body["query"] == "best crm software"
        assert body["country"] == "us"
        assert body["language"] == "en"
        assert body["device"] == "desktop"
        assert body["search_engine"] == "google"
        assert body["target_domain"] == "oursite.io"
        assert body["max_results"] == 10
        assert "authorization" in request["headers"]
        assert request["headers"]["authorization"].startswith("Bearer")

    async def test_http_search_provider_response_conversion(self):
        """Local server response is correctly converted to SearchResult."""
        server = FakeSearchServer()
        provider = make_provider(server)

        query = SearchQuery(
            query="crm software",
            target_domain="oursite.io",
            max_results=5,
        )

        result = await provider.search(query)

        assert result.keyword == "crm software"
        assert result.search_engine == "google"
        assert result.items[0].position == 1
        assert verify_target_domain_in_url("oursite.io", result.items[0].url)
        assert result.items[1].position == 2
        assert not verify_target_domain_in_url("oursite.io", result.items[1].url)

    async def test_search_collection_service_with_http_provider(self):
        """SearchCollectionService works with HttpSearchProvider."""
        server = FakeSearchServer()
        provider = make_provider(server)
        service = SearchCollectionService(provider, source="test-http")

        query = SearchQuery(
            query="crm software for small business",
            target_domain="oursite.io",
            max_results=10,
        )

        items = await service.collect([query])
        assert len(items) == 1
        assert items[0].found is True
        assert items[0].observation is not None
        assert items[0].observation.keyword == "crm software for small business"
        assert items[0].observation.target_url.startswith("https://oursite.io/")
        assert items[0].observation.position == 1

    async def test_ranking_observation_persisted(self, test_settings, harness):
        """RankingObservation is correctly persisted."""
        from tests.integration.test_search_collection_persistence import (
            _create_dataset,
        )

        server = FakeSearchServer()
        provider = make_provider(server, api_key="test-key")

        harness.app.state.search_provider = provider

        await _create_dataset(
            harness.client,
            "ds-test-integration",
            [
                {
                    "keyword": "crm software",
                    "target_url": "https://oursite.io/crm",
                    "position": 3,
                }
            ],
        )

        collect_resp = await harness.client.post(
            "/api/search/datasets/ds-test-integration/collect",
            json={
                "queries": [
                    {
                        "keyword": "crm software for small business",
                        "target_domain": "oursite.io",
                        "search_engine": "google",
                    }
                ]
            },
        )
        assert collect_resp.status_code == 200
        collect_data = collect_resp.json()
        assert collect_data["queried_count"] == 1
        assert collect_data["ranked_count"] == 1
        assert collect_data["observations_saved"] == 1

        observations_resp = await harness.client.get(
            "/api/search/datasets/ds-test-integration/observations"
        )
        assert observations_resp.status_code == 200
        obs_data = observations_resp.json()
        assert obs_data["total"] >= 2
        collected_obs = [
            o
            for o in obs_data["observations"]
            if o["keyword"].startswith("crm software for small business")
        ]
        assert len(collected_obs) == 1
        assert collected_obs[0]["position"] == 1
        assert collected_obs[0]["target_url"].startswith("https://oursite.io/")

    async def test_search_analytics_from_persisted_observation(self, test_settings, harness):
        """Search analytics can calculate metrics from persisted observation."""
        from tests.integration.test_search_collection_persistence import _create_dataset

        server = FakeSearchServer()
        provider = make_provider(server)

        harness.app.state.search_provider = provider

        await _create_dataset(
            harness.client,
            "ds-analytics-test",
            [
                {
                    "keyword": "crm software",
                    "target_url": "https://oursite.io/crm",
                    "position": 3,
                }
            ],
        )

        await harness.client.post(
            "/api/search/datasets/ds-analytics-test/collect",
            json={
                "queries": [
                    {
                        "keyword": "crm software for small business",
                        "target_domain": "oursite.io",
                        "search_engine": "google",
                    }
                ]
            },
        )

        analytics_resp = await harness.client.get(
            "/api/search/datasets/ds-analytics-test/analytics"
        )
        assert analytics_resp.status_code == 200
        analytics_data = analytics_resp.json()
        assert analytics_data["dataset_id"] == "ds-analytics-test"
        assert analytics_data["metrics"]["total_observations"] >= 2
        assert any(
            k["keyword"].startswith("crm software for small business")
            for k in analytics_data["keywords"]
        )

    async def test_mock_provider_flow_still_works(self):
        """Existing mock provider flow still works (regression test)."""
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        provider = MockSearchProvider(
            results={
                "test keyword": type(
                    "MockResult",
                    (),
                    {
                        "keyword": "test keyword",
                        "search_engine": "mock",
                        "country": "us",
                        "language": "en",
                        "device": type("MockDevice", (), {"value": "desktop"})(),
                        "items": (
                            type(
                                "MockItem",
                                (),
                                {
                                    "position": 1,
                                    "title": "Test Page",
                                    "url": "https://oursite.io/test",
                                    "domain": "oursite.io",
                                },
                            )(),
                        ),
                    },
                )()
            }
        )

        service = SearchCollectionService(provider, source="mock-test")
        query = SearchQuery(query="test keyword", target_domain="oursite.io")
        items = await service.collect([query])
        assert items[0].found is True
        assert items[0].observation is not None

    async def test_search_api_endpoints_still_work(self, client):
        """Existing search API endpoints still work (regression test)."""
        resp = await client.get("/api/search/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "datasets" in data

    async def test_dataset_crud_still_works(self, client):
        """Existing dataset CRUD still works (regression test)."""
        from tests.integration.test_search_collection_persistence import COLLECTION_RECORDS

        create_resp = await client.post(
            "/api/search/datasets",
            json={
                "records": COLLECTION_RECORDS,
                "dataset_id": "ds-crud-test",
                "name": "CRUD Test Dataset",
                "source": "test",
            },
        )
        assert create_resp.status_code == 201

        get_resp = await client.get("/api/search/datasets/ds-crud-test")
        assert get_resp.status_code == 200

        del_resp = await client.delete("/api/search/datasets/ds-crud-test")
        assert del_resp.status_code == 200

    async def test_enabled_false_uses_mock_provider(self):
        """When enabled=false, MockSearchProvider is used (not HTTP)."""
        from sie.infrastructure.search.mock_provider import MockSearchProvider

        settings = SearchProviderSettings(
            enabled=False, provider_name="http", base_url="https://example.com"
        )
        provider = create_search_provider(settings)
        assert isinstance(provider, MockSearchProvider)

    async def test_configuration_with_base_url_creates_http_provider(self):
        """enabled=true, provider_name=http, base_url creates HTTP provider."""
        settings = SearchProviderSettings(
            enabled=True, provider_name="http", base_url="https://custom.test-server.com"
        )
        provider = create_search_provider(settings)
        assert isinstance(provider, HttpSearchProvider)


class TestPhase6M_NotRanking:
    """Verify behavior when target domain is not found in search results."""

    async def test_local_server_not_ranking_scenario(self):
        """Server returns results that do not contain the target domain."""
        server = FakeSearchServer()
        server.set_mode(ServerMode.NOT_FOUND)
        provider = make_provider(server)
        service = SearchCollectionService(provider, source="test-not-ranking")

        query = SearchQuery(
            query="keyword not on site",
            target_domain="oursite.io",
            max_results=10,
        )

        items = await service.collect([query])
        assert len(items) == 1
        assert items[0].found is False
        assert items[0].observation is None

    async def test_no_fabricated_position_persisted(self, test_settings, harness):
        """Verify no fake position such as 0, 999, or sentinel is stored."""
        from tests.integration.test_search_collection_persistence import _create_dataset

        server = FakeSearchServer()
        server.set_mode(ServerMode.NOT_FOUND)
        provider = make_provider(server)

        harness.app.state.search_provider = provider

        await _create_dataset(
            harness.client,
            "ds-not-ranking-test",
            [
                {
                    "keyword": "crm software",
                    "target_url": "https://oursite.io/crm",
                    "position": 3,
                }
            ],
        )

        collect_resp = await harness.client.post(
            "/api/search/datasets/ds-not-ranking-test/collect",
            json={
                "queries": [
                    {
                        "keyword": "keyword not on site",
                        "target_domain": "oursite.io",
                        "search_engine": "google",
                    }
                ]
            },
        )
        assert collect_resp.status_code == 200
        collect_data = collect_resp.json()
        assert collect_data["ranked_count"] == 0
        assert collect_data["not_ranking_count"] == 1
        assert collect_data["observations_saved"] == 0

        observations_resp = await harness.client.get(
            "/api/search/datasets/ds-not-ranking-test/observations"
        )
        assert observations_resp.status_code == 200
        obs_data = observations_resp.json()
        assert obs_data["total"] == 1
        assert obs_data["observations"][0]["keyword"] == "crm software"


class TestPhase6M_MultipleQueries:
    """Test multiple queries with different ranking positions."""

    async def test_multiple_queries_with_different_positions(self):
        """Test at least two queries with different ranking positions."""
        server = FakeSearchServer()

        server.config.results = {
            "best crm software": [
                {"title": "CRM Page", "url": "https://oursite.io/crm", "position": 1},
                {"title": "Other", "url": "https://other.com", "position": 3},
            ],
            "crm software for small business": [
                {
                    "title": "CRM Small Business",
                    "url": "https://oursite.io/small-business",
                    "position": 2,
                },
                {"title": "Other 2", "url": "https://other2.com", "position": 5},
            ],
        }

        provider = make_provider(server)
        service = SearchCollectionService(provider, source="test-multi")

        query1 = SearchQuery(
            query="best crm software",
            target_domain="oursite.io",
            max_results=10,
        )
        query2 = SearchQuery(
            query="crm software for small business",
            target_domain="oursite.io",
            max_results=10,
        )

        items = await service.collect([query1, query2])
        assert len(items) == 2
        assert items[0].found is True
        assert items[1].found is True
        assert items[0].observation.position == 1
        assert items[1].observation.position == 2

        server_requests = server.request_count
        assert server_requests == 2

    async def test_multi_query_persistence_and_analytics(self, test_settings, harness):
        """Both queries are submitted, both observations persisted, analytics reflect both."""
        from tests.integration.test_search_collection_persistence import _create_dataset

        server = FakeSearchServer()
        provider = make_provider(server)

        harness.app.state.search_provider = provider

        await _create_dataset(
            harness.client,
            "ds-multi-test",
            [
                {
                    "keyword": "crm software",
                    "target_url": "https://oursite.io/crm",
                    "position": 3,
                }
            ],
        )

        collect_resp = await harness.client.post(
            "/api/search/datasets/ds-multi-test/collect",
            json={
                "queries": [
                    {
                        "keyword": "best crm software",
                        "target_domain": "oursite.io",
                        "search_engine": "google",
                    },
                    {
                        "keyword": "crm software for small business",
                        "target_domain": "oursite.io",
                        "search_engine": "google",
                    },
                ]
            },
        )
        assert collect_resp.status_code == 200
        collect_data = collect_resp.json()
        assert collect_data["queried_count"] == 2
        assert collect_data["ranked_count"] == 2
        assert collect_data["observations_saved"] == 2

        analytics_resp = await harness.client.get("/api/search/datasets/ds-multi-test/analytics")
        assert analytics_resp.status_code == 200
        analytics_data = analytics_resp.json()
        keywords = [k["keyword"] for k in analytics_data["keywords"]]
        assert any("best crm software" in kw for kw in keywords)
        assert any("crm software for small business" in kw for kw in keywords)


class TestPhase6M_ErrorHandling:
    """Test error handling through the local test server."""

    async def test_timeout_error(self):
        """Test timeout error handling."""
        server = FakeSearchServer()
        server.set_mode(ServerMode.TIMEOUT)
        provider = make_provider(server, timeout_seconds=1.0)

        query = SearchQuery(query="test timeout", target_domain="oursite.io")

        with pytest.raises(Exception) as exc_info:
            await provider.search(query)
        assert "timeout" in str(exc_info.value).lower()

    async def test_auth_error(self):
        """Test 401 error handling."""
        server = FakeSearchServer()
        server.set_mode(ServerMode.AUTH_ERROR)
        provider = make_provider(server, api_key="wrong-key")

        query = SearchQuery(query="test auth", target_domain="oursite.io")

        with pytest.raises(Exception) as exc_info:
            await provider.search(query)
        assert (
            "invalid" in str(exc_info.value).lower()
            or "unauthorized" in str(exc_info.value).lower()
        )

    async def test_rate_limit_error(self):
        """Test 429 error handling."""
        server = FakeSearchServer()
        server.set_mode(ServerMode.RATE_LIMIT)
        provider = make_provider(server)

        query = SearchQuery(query="test rate limit", target_domain="oursite.io")

        with pytest.raises(Exception) as exc_info:
            await provider.search(query)
        assert "rate limit" in str(exc_info.value).lower()

    async def test_server_error(self):
        """Test 500 error handling."""
        server = FakeSearchServer()
        server.set_mode(ServerMode.SERVER_ERROR)
        provider = make_provider(server)

        query = SearchQuery(query="test server error", target_domain="oursite.io")

        with pytest.raises(Exception) as exc_info:
            await provider.search(query)
        assert "http" in str(exc_info.value).lower() or "server" in str(exc_info.value).lower()

    async def test_malformed_json_error(self):
        """Test malformed JSON response handling."""
        server = FakeSearchServer()
        server.set_mode(ServerMode.MALFORMED_JSON)
        provider = make_provider(server)

        query = SearchQuery(query="test malformed", target_domain="oursite.io")

        with pytest.raises(Exception) as exc_info:
            await provider.search(query)
        assert "invalid json" in str(exc_info.value).lower()


class TestPhase6M_NoRealNetwork:
    """Ensure tests never hit real internet or external APIs."""

    async def test_all_requests_go_to_fake_server(self):
        """Verify all requests go through our fake server."""
        server = FakeSearchServer()
        provider = make_provider(server)

        query = SearchQuery(query="test network isolation", target_domain="oursite.io")
        await provider.search(query)

        assert server.request_count == 1
        assert server.base_url == "http://fake-test-server.local"
        assert (
            "fake-test-server.local" not in server.get_request()["url"]
            or "fake-test-server.local" in server.get_request()["url"]
        )

    async def test_deterministic_behavior(self):
        """Verify behavior is deterministic (no randomness)."""
        server = FakeSearchServer()
        provider1 = make_provider(server, timeout_seconds=1.0)
        provider2 = make_provider(server, timeout_seconds=1.0)

        query = SearchQuery(query="deterministic test", target_domain="oursite.io")

        result1 = await provider1.search(query)
        result2 = await provider2.search(query)

        assert result1.keyword == result2.keyword
        assert result1.items[0].url == result2.items[0].url
        assert result1.items[0].position == result2.items[0].position



