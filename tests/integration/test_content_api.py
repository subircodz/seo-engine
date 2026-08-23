"""Integration tests for Content API endpoints."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_crawl_pages():
    """Create sample fetched pages for testing."""
    from sie.domain.models.page import FetchedPage

    return [
        FetchedPage(
            url="https://example.com/page1",
            final_url="https://example.com/page1",
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"""
            <html>
            <head><title>Page 1 - SEO Guide</title><meta name="description" content="Learn SEO basics"></head>
            <body>
                <h1>Complete SEO Guide</h1>
                <p>This is a comprehensive guide to search engine optimization.</p>
                <h2>Keywords</h2>
                <p>Keywords are important for SEO. Use them naturally in content.</p>
                <h2>Links</h2>
                <p>Internal links help crawlers. <a href="/page2">Link to page 2</a></p>
                <img src="/img1.jpg" alt="SEO diagram">
            </body>
            </html>
            """,
            content_type="text/html",
            depth=0,
        ),
        FetchedPage(
            url="https://example.com/page2",
            final_url="https://example.com/page2",
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"""
            <html>
            <head><title>Page 2 - Advanced SEO</title><meta name="description" content="Advanced SEO tactics"></head>
            <body>
                <h1>Advanced SEO Tactics</h1>
                <p>Advanced strategies for improving rankings.</p>
                <h2>Technical SEO</h2>
                <p>Site speed and crawlability matter.</p>
                <img src="/img2.jpg" alt="Technical SEO chart">
            </body>
            </html>
            """,
            content_type="text/html",
            depth=1,
        ),
    ]


@pytest.fixture
async def crawl_with_pages(harness, sample_crawl_pages):
    """Start a crawl run and inject sample pages."""
    app = harness.app
    client = harness.client

    # Start crawl
    resp = await client.post("/api/crawl", json={"url": "https://example.com", "max_pages": 10})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    # Inject pages directly into app state
    app.state.crawled_pages[run_id] = sample_crawl_pages

    return run_id


class TestContentAnalysisAPI:
    """Test /api/content/analyze endpoints."""

    @pytest.mark.asyncio
    async def test_analyze_content(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client

        resp = await client.post(
            "/api/content/analyze",
            json={"run_id": run_id, "config": {"min_word_count": 100}},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["run_id"] == run_id
        assert data["status"] == "completed"
        assert data["total_pages"] == 2
        assert data["analyzed_pages"] == 2
        assert "avg_quality_score" in data
        assert len(data["items"]) == 2

        # Check first page
        item = data["items"][0]
        assert "url" in item
        assert "content_type" in item
        assert "word_count" in item
        assert "quality_score" in item
        assert "quality_tier" in item

    @pytest.mark.asyncio
    async def test_get_content_analysis(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client

        # First run analysis
        await client.post("/api/content/analyze", json={"run_id": run_id})

        # Then retrieve
        resp = await client.get(f"/api/content/analyze/{run_id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["run_id"] == run_id
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_content_pages_paginated(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/analyze", json={"run_id": run_id})

        resp = await client.get(
            f"/api/content/analyze/{run_id}/pages", params={"limit": 1, "offset": 0}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        resp = await client.get(
            f"/api/content/analyze/{run_id}/pages", params={"limit": 1, "offset": 1}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_get_page_metrics(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/analyze", json={"run_id": run_id})

        resp = await client.get(f"/api/content/analyze/{run_id}/pages/https://example.com/page1")
        assert resp.status_code == 200
        data = resp.json()

        assert data["url"] == "https://example.com/page1"
        assert "readability" in data
        assert "headings" in data
        assert "images" in data
        assert "links" in data
        assert "structured_data" in data
        assert "freshness" in data
        assert "multimedia" in data
        assert "keywords" in data

    @pytest.mark.asyncio
    async def test_get_page_metrics_not_found(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/analyze", json={"run_id": run_id})

        resp = await client.get(
            f"/api/content/analyze/{run_id}/pages/https://example.com/nonexistent"
        )
        assert resp.status_code == 404


class TestContentComparisonAPI:
    """Test /api/content/compare endpoints."""

    @pytest.mark.asyncio
    async def test_compare_content(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client

        resp = await client.post("/api/content/compare", json={"run_id": run_id})
        assert resp.status_code == 200
        data = resp.json()

        assert data["run_id"] == run_id
        assert "total" in data
        assert "items" in data

    @pytest.mark.asyncio
    async def test_get_comparisons(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/compare", json={"run_id": run_id})

        resp = await client.get(f"/api/content/compare/{run_id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["run_id"] == run_id
        assert "items" in data

    @pytest.mark.asyncio
    async def test_get_duplicates(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/compare", json={"run_id": run_id})

        resp = await client.get(f"/api/content/compare/{run_id}/duplicates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestContentQualityReportAPI:
    """Test /api/content/quality-report endpoints."""

    @pytest.mark.asyncio
    async def test_generate_quality_report(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client

        resp = await client.post("/api/content/quality-report", json={"run_id": run_id})
        assert resp.status_code == 200
        data = resp.json()

        assert data["run_id"] == run_id
        assert data["total_pages"] == 2
        assert "avg_quality_score" in data
        assert "quality_distribution" in data
        assert "thin_content_pages" in data
        assert "duplicate_groups" in data
        assert "top_issues" in data

    @pytest.mark.asyncio
    async def test_get_quality_report(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/quality-report", json={"run_id": run_id})

        resp = await client.get(f"/api/content/quality-report/{run_id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["run_id"] == run_id
        assert data["total_pages"] == 2


class TestContentFilterEndpoints:
    """Test filtering endpoints."""

    @pytest.mark.asyncio
    async def test_get_pages_by_type(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/analyze", json={"run_id": run_id})

        resp = await client.get(f"/api/content/analyze/{run_id}/by-type/article")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_pages_by_invalid_type(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/analyze", json={"run_id": run_id})

        resp = await client.get(f"/api/content/analyze/{run_id}/by-type/invalid_type")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_get_pages_by_quality(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/analyze", json={"run_id": run_id})

        resp = await client.get(f"/api/content/analyze/{run_id}/by-quality/good")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_pages_by_invalid_quality(self, harness, crawl_with_pages):
        run_id = crawl_with_pages
        client = harness.client
        await client.post("/api/content/analyze", json={"run_id": run_id})

        resp = await client.get(f"/api/content/analyze/{run_id}/by-quality/invalid")
        assert resp.status_code == 400
