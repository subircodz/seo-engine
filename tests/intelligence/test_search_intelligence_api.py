"""Integration tests for Search Intelligence API endpoints (Phase 7)."""

import pytest
from httpx import ASGITransport, AsyncClient

from sie.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── AIO Analysis ─────────────────────────────────────────────────────────


class TestAIOAnalysis:
    @pytest.mark.anyio
    async def test_aio_analyze_empty(self, client):
        response = await client.post(
            "/api/search-intelligence/aio/analyze",
            json={
                "dataset_id": "test-1",
                "observations": [],
                "total_keywords": 0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "test-1"
        assert data["keyword_metrics"] == []
        assert data["dataset_metrics"]["total_keywords"] == 0

    @pytest.mark.anyio
    async def test_aio_analyze_with_observations(self, client):
        response = await client.post(
            "/api/search-intelligence/aio/analyze",
            json={
                "dataset_id": "test-2",
                "observations": [
                    {
                        "keyword": "seo tools",
                        "ai_type": "ai_overview",
                        "present": True,
                        "target_cited": True,
                        "target_domain": "oursite.io",
                        "citation_count": 3,
                        "competitor_cited_domains": ["comp1.com"],
                    },
                    {
                        "keyword": "seo tools",
                        "ai_type": "ai_overview",
                        "present": True,
                        "target_cited": False,
                        "competitor_cited_domains": ["comp2.com"],
                    },
                ],
                "total_keywords": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "test-2"
        assert len(data["keyword_metrics"]) == 1
        assert data["keyword_metrics"][0]["keyword"] == "seo tools"
        assert data["keyword_metrics"][0]["ai_overview_present_count"] == 2
        assert data["keyword_metrics"][0]["target_cited_count"] == 1
        assert data["dataset_metrics"]["total_keywords"] == 5
        assert data["dataset_metrics"]["keywords_with_ai_overview"] == 1


# ── GEO Analysis ─────────────────────────────────────────────────────────


class TestGEOAnalysis:
    @pytest.mark.anyio
    async def test_geo_analyze_empty(self, client):
        response = await client.post(
            "/api/search-intelligence/geo/analyze",
            json={
                "dataset_id": "test-1",
                "observations": [],
                "total_keywords": 0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "test-1"
        assert data["keyword_metrics"] == []

    @pytest.mark.anyio
    async def test_geo_analyze_with_observations(self, client):
        response = await client.post(
            "/api/search-intelligence/geo/analyze",
            json={
                "dataset_id": "test-2",
                "observations": [
                    {
                        "keyword": "best seo tools",
                        "engine_type": "perplexity",
                        "target_mentioned": True,
                        "target_domain": "oursite.io",
                        "mention_count": 2,
                        "competitor_domains": ["comp1.com"],
                    },
                    {
                        "keyword": "best seo tools",
                        "engine_type": "perplexity",
                        "target_mentioned": False,
                        "competitor_domains": ["comp2.com"],
                    },
                ],
                "total_keywords": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "test-2"
        assert len(data["keyword_metrics"]) == 1
        assert data["keyword_metrics"][0]["target_mentioned_count"] == 1
        assert data["dataset_metrics"]["total_keywords"] == 3


# ── Cannibalization Analysis ─────────────────────────────────────────────


class TestCannibalizationAnalysis:
    @pytest.mark.anyio
    async def test_cannibalization_empty(self, client):
        response = await client.post(
            "/api/search-intelligence/cannibalization/analyze",
            json={"dataset_id": "test-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_findings"] == 0

    @pytest.mark.anyio
    async def test_cannibalization_with_data(self, client):
        response = await client.post(
            "/api/search-intelligence/cannibalization/analyze",
            json={
                "dataset_id": "test-2",
                "observations": [
                    {"keyword": "kw1", "target_url": "https://oursite.io/p1", "position": 5},
                    {"keyword": "kw1", "target_url": "https://oursite.io/p2", "position": 8},
                    {"keyword": "kw1", "target_url": "https://oursite.io/p3", "position": 12},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_findings"] > 0
        assert data["keywords_affected"] > 0


# ── Volatility Analysis ──────────────────────────────────────────────────


class TestVolatilityAnalysis:
    @pytest.mark.anyio
    async def test_volatility_empty(self, client):
        response = await client.post(
            "/api/search-intelligence/volatility/analyze",
            json={"dataset_id": "test-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_keywords"] == 0
        assert data["volatile_count"] == 0

    @pytest.mark.anyio
    async def test_volatility_with_data(self, client):
        response = await client.post(
            "/api/search-intelligence/volatility/analyze",
            json={
                "dataset_id": "test-2",
                "observations": [
                    {"keyword": "kw1", "position": 2},
                    {"keyword": "kw1", "position": 20},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_keywords"] == 1
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["keyword"] == "kw1"


# ── Opportunity Analysis ─────────────────────────────────────────────────


class TestOpportunityAnalysis:
    @pytest.mark.anyio
    async def test_opportunities_empty(self, client):
        response = await client.post(
            "/api/search-intelligence/opportunities/analyze",
            json={"dataset_id": "test-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_opportunities"] == 0

    @pytest.mark.anyio
    async def test_opportunities_with_data(self, client):
        response = await client.post(
            "/api/search-intelligence/opportunities/analyze",
            json={
                "dataset_id": "test-2",
                "observations": [
                    {"keyword": "kw1", "target_url": "https://oursite.io/", "position": 5},
                ],
                "competitor_rankings": [
                    {
                        "keyword": "kw1",
                        "competitor_domain": "comp1.com",
                        "competitor_url": "https://comp1.com/",
                        "position": 3,
                    },
                    {
                        "keyword": "kw1",
                        "competitor_domain": "comp2.com",
                        "competitor_url": "https://comp2.com/",
                        "position": 7,
                    },
                ],
                "total_keywords": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "competitor_gaps" in data
        assert "weak_ranking_opportunities" in data
        assert "content_gaps" in data


# ── Unified Search Intelligence ──────────────────────────────────────────


class TestSearchIntelligence:
    @pytest.mark.anyio
    async def test_intelligence_empty(self, client):
        response = await client.post(
            "/api/search-intelligence/analyze",
            json={"dataset_id": "test-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "test-1"
        assert "summary" in data
        assert "recommendations" in data

    @pytest.mark.anyio
    async def test_intelligence_with_data(self, client):
        response = await client.post(
            "/api/search-intelligence/analyze",
            json={
                "dataset_id": "test-2",
                "observations": [
                    {"keyword": "kw1", "target_url": "https://oursite.io/", "position": 5},
                    {"keyword": "kw2", "target_url": "https://oursite.io/", "position": 15},
                ],
                "competitor_rankings": [
                    {
                        "keyword": "kw1",
                        "competitor_domain": "comp1.com",
                        "competitor_url": "https://comp1.com/",
                        "position": 3,
                    },
                ],
                "total_keywords": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "test-2"
        assert data["summary"]["total_keywords"] == 2
        assert isinstance(data["recommendations"], list)
