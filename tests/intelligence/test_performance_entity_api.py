"""Integration tests for Performance, Entity, Optimization, and Report API endpoints (Phase 8)."""

from __future__ import annotations

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


# ════════════════════════════════════════════════════════════════════════════
# Performance endpoint
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestPerformanceEndpoint:
    async def test_empty_request(self, client):
        resp = await client.post(
            "/api/search-intelligence/performance/analyze",
            json={"dataset_id": "test", "pages": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset_id"] == "test"
        assert data["total_pages"] == 0

    async def test_single_page(self, client):
        resp = await client.post(
            "/api/search-intelligence/performance/analyze",
            json={
                "dataset_id": "test",
                "pages": [
                    {
                        "url": "http://example.com",
                        "html_size": 50000,
                        "visible_text": "Hello world content",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_pages"] == 1
        assert data["avg_html_size"] == 50000.0

    async def test_multiple_pages(self, client):
        resp = await client.post(
            "/api/search-intelligence/performance/analyze",
            json={
                "dataset_id": "test",
                "pages": [
                    {"url": "http://a.com", "html_size": 10000},
                    {"url": "http://b.com", "html_size": 20000},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_pages"] == 2
        assert data["avg_html_size"] == 15000.0


# ════════════════════════════════════════════════════════════════════════════
# Entity extraction endpoint
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestEntityExtractionEndpoint:
    async def test_empty_text(self, client):
        resp = await client.post(
            "/api/search-intelligence/entity/extract",
            json={"text": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entities"] == 0

    async def test_basic_extraction(self, client):
        resp = await client.post(
            "/api/search-intelligence/entity/extract",
            json={
                "text": (
                    "Acme Corp announced new products. "
                    "Acme Corp released a major update."
                )
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entities"] >= 1


# ════════════════════════════════════════════════════════════════════════════
# Entity analysis endpoint
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestEntityAnalysisEndpoint:
    async def test_empty_observations(self, client):
        resp = await client.post(
            "/api/search-intelligence/entity/analyze",
            json={"dataset_id": "test", "observations": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_unique_entities"] == 0

    async def test_with_observations(self, client):
        resp = await client.post(
            "/api/search-intelligence/entity/analyze",
            json={
                "dataset_id": "test",
                "observations": [
                    {
                        "keyword": "test query",
                        "content_text": "Acme Corp makes great products.",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["keyword_count"] == 1


# ════════════════════════════════════════════════════════════════════════════
# Entity gaps endpoint
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestEntityGapsEndpoint:
    async def test_no_gaps(self, client):
        resp = await client.post(
            "/api/search-intelligence/entity/gaps",
            json={
                "target_entities": [{"text": "Acme", "frequency": 5}],
                "competitor_entities": [{"text": "Acme", "frequency": 3}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_gaps"] == 0

    async def test_with_gaps(self, client):
        resp = await client.post(
            "/api/search-intelligence/entity/gaps",
            json={
                "target_entities": [{"text": "Acme", "frequency": 5}],
                "competitor_entities": [
                    {"text": "Rival", "frequency": 5},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_gaps"] == 1


# ════════════════════════════════════════════════════════════════════════════
# Optimization endpoint
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestOptimizationEndpoint:
    async def test_empty_request(self, client):
        resp = await client.post(
            "/api/search-intelligence/optimization/analyze",
            json={"dataset_id": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_recommendations"] == 0

    async def test_with_ranking_issues(self, client):
        resp = await client.post(
            "/api/search-intelligence/optimization/analyze",
            json={
                "dataset_id": "test",
                "total_keywords": 100,
                "keywords_not_ranking": 60,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_recommendations"] >= 1
        assert len(data["summary"]) > 0


# ════════════════════════════════════════════════════════════════════════════
# Report endpoint
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestReportEndpoint:
    async def test_empty_request(self, client):
        resp = await client.post(
            "/api/search-intelligence/report",
            json={"dataset_id": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset_id"] == "test"
        assert data["component_count"] == 0

    async def test_with_data(self, client):
        resp = await client.post(
            "/api/search-intelligence/report",
            json={
                "dataset_id": "test",
                "total_keywords": 100,
                "keywords_not_ranking": 20,
                "cannibalization_count": 5,
                "volatile_keyword_count": 10,
                "performance_total_pages": 50,
                "entity_total_unique": 30,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["component_count"] >= 3
        assert len(data["summary"]) > 0
