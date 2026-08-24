"""Integration tests for Diagnosis API endpoints."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_crawl_pages():
    """Create sample fetched pages for testing."""
    from sie.domain.models.page import FetchedPage

    return [
        FetchedPage(
            url="https://example.com/good-page",
            final_url="https://example.com/good-page",
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"""
            <html>
            <head>
                <title>Good Page - SEO Guide</title>
                <meta name="description" content="Learn SEO basics">
            </head>
            <body>
                <h1>Complete SEO Guide</h1>
                <p>This is a comprehensive guide to SEO with enough content.</p>
                <h2>Keywords</h2>
                <p>Keywords are important for SEO. Use them naturally.</p>
                <h2>Links</h2>
                <p>Internal links help crawlers. <a href="/bad-page">Link</a></p>
                <img src="/img1.jpg" alt="SEO diagram">
            </body>
            </html>
            """,
            content_type="text/html",
            depth=0,
        ),
        FetchedPage(
            url="https://example.com/bad-page",
            final_url="https://example.com/bad-page",
            status_code=404,
            headers={"Content-Type": "text/html"},
            content=b"<html><body><h1>Not Found</h1></body></html>",
            content_type="text/html",
            depth=1,
        ),
        FetchedPage(
            url="https://example.com/thin-page",
            final_url="https://example.com/thin-page",
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"""
            <html>
            <body>
                <p>Short content.</p>
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


class TestDiagnosisAPI:
    """Test /api/diagnosis/* endpoints."""

    @pytest.mark.asyncio
    async def test_run_diagnosis(self, harness, crawl_with_pages):
        client = harness.client
        run_id = crawl_with_pages

        resp = await client.post(
            "/api/diagnosis/run",
            json={"run_id": run_id, "priorities": ["P0", "P1", "P2", "P3"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["status"] == "completed"
        assert data["total_issues"] > 0
        assert "issues_by_priority" in data
        assert "issues_by_severity" in data
        assert "issues_by_category" in data

    @pytest.mark.asyncio
    async def test_get_diagnosis(self, harness, crawl_with_pages):
        client = harness.client
        run_id = crawl_with_pages

        # Run diagnosis first
        await client.post(
            "/api/diagnosis/run",
            json={"run_id": run_id},
        )

        # Get cached result
        resp = await client.get(f"/api/diagnosis/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["total_issues"] > 0

    @pytest.mark.asyncio
    async def test_get_diagnosis_not_found(self, harness):
        client = harness.client
        resp = await client.get("/api/diagnosis/nonexistent-run")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_diagnosis_issues(self, harness, crawl_with_pages):
        client = harness.client
        run_id = crawl_with_pages

        # Run diagnosis first
        await client.post(
            "/api/diagnosis/run",
            json={"run_id": run_id},
        )

        # Get issues list
        resp = await client.get(f"/api/diagnosis/{run_id}/issues")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert len(data["items"]) > 0

        # Check issue structure
        issue = data["items"][0]
        assert "rule_code" in issue
        assert "category" in issue
        assert "severity" in issue
        assert "priority" in issue
        assert "affected_url" in issue
        assert "explanation" in issue
        assert "recommendation" in issue
        assert "evidence" in issue
        assert "confidence" in issue
        assert "source_engine" in issue

    @pytest.mark.asyncio
    async def test_get_diagnosis_issues_with_filters(self, harness, crawl_with_pages):
        client = harness.client
        run_id = crawl_with_pages

        # Run diagnosis first
        await client.post(
            "/api/diagnosis/run",
            json={"run_id": run_id},
        )

        # Filter by severity
        resp = await client.get(
            f"/api/diagnosis/{run_id}/issues",
            params={"severity": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert all(item["severity"] == "critical" for item in data["items"])

        # Filter by priority
        resp = await client.get(
            f"/api/diagnosis/{run_id}/issues",
            params={"priority": "P0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert all(item["priority"] == "P0" for item in data["items"])

    @pytest.mark.asyncio
    async def test_run_diagnosis_not_found(self, harness):
        client = harness.client
        resp = await client.post(
            "/api/diagnosis/run",
            json={"run_id": "nonexistent-run"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_diagnosis_detects_broken_page(self, harness, crawl_with_pages):
        """Verify diagnosis detects the 404 page in the sample data."""
        client = harness.client
        run_id = crawl_with_pages

        resp = await client.post(
            "/api/diagnosis/run",
            json={"run_id": run_id},
        )
        assert resp.status_code == 200

        # Should detect the broken page
        issues_resp = await client.get(f"/api/diagnosis/{run_id}/issues")
        issues_data = issues_resp.json()
        broken_issues = [i for i in issues_data["items"] if i["rule_code"] == "DX_BROKEN_PAGE"]
        assert len(broken_issues) >= 1
        assert any("bad-page" in i["affected_url"] for i in broken_issues)

    @pytest.mark.asyncio
    async def test_diagnosis_detects_thin_content(self, harness, crawl_with_pages):
        """Verify diagnosis detects thin content pages."""
        client = harness.client
        run_id = crawl_with_pages

        resp = await client.post(
            "/api/diagnosis/run",
            json={"run_id": run_id},
        )
        assert resp.status_code == 200

        issues_resp = await client.get(f"/api/diagnosis/{run_id}/issues")
        issues_data = issues_resp.json()
        thin_issues = [i for i in issues_data["items"] if i["rule_code"] == "DX_THIN_CONTENT"]
        assert len(thin_issues) >= 1
        assert any("thin-page" in i["affected_url"] for i in thin_issues)
