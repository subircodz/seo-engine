"""End-to-end API tests: auto-migration, crawl lifecycle, history, pagination."""

import sqlite3

from sie.domain.models.crawl import CrawlStatus
from sie.domain.models.page import FetchedPage
from tests.fakes import FakeCrawler


async def test_startup_auto_migration_creates_schema(test_settings, tmp_path):
    """Regression guard: auto-migrate must work inside a running event loop."""
    from sie.api.app import create_app

    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        pass  # lifespan startup runs migrations; shutdown cleans up
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "crawl_runs" in tables and "crawl_pages" in tables
        run_cols = {r[1] for r in conn.execute("PRAGMA table_info(crawl_runs)")}
        page_cols = {r[1] for r in conn.execute("PRAGMA table_info(crawl_pages)")}
        assert {"total_pages", "error_count"} <= run_cols
        assert {"content_type", "depth", "parent_url"} <= page_cols
    finally:
        conn.close()


def _inject_crawler(harness, crawler):
    """Swap the engine behind the service (test-only seam)."""
    service = harness.app.state.crawl_service
    assert hasattr(service, "_crawler")
    service._crawler = crawler


async def test_full_crawl_lifecycle_via_api(harness):
    """POST -> poll -> pages -> history with the fake crawler injected."""
    pages = [
        FetchedPage(
            url=f"https://example.com/p{i}",
            final_url=f"https://example.com/p{i}",
            status_code=200,
            headers={},
            content=b"x" * (10 + i),
            content_type="text/html",
            depth=i,
            parent_url="https://example.com/p0" if i else None,
        )
        for i in range(3)
    ]
    _inject_crawler(harness, FakeCrawler(pages))
    client = harness.client

    start = await client.post(
        "/api/crawl",
        json={"url": "https://example.com/", "max_pages": 5, "depth_limit": 2},
    )
    assert start.status_code == 202
    run_id = start.json()["run_id"]

    detail = await client.get(f"/api/crawl/{run_id}")
    for _ in range(100):
        detail = await client.get(f"/api/crawl/{run_id}")
        if detail.json()["status"] == CrawlStatus.COMPLETED.value:
            break
    body = detail.json()
    assert body["status"] == CrawlStatus.COMPLETED.value
    assert body["stats"]["pages_fetched"] == 3
    assert body["pages_stored"] == 3

    listing = await client.get(f"/api/crawl/{run_id}/pages?limit=2&offset=0")
    assert listing.status_code == 200
    data = listing.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["items"][0]["depth"] == 0
    assert data["items"][0]["content_type"] is not None
    assert data["items"][1]["parent_url"] == "https://example.com/p0"

    page_two = await client.get(f"/api/crawl/{run_id}/pages?limit=2&offset=2")
    assert len(page_two.json()["items"]) == 1

    history = await client.get("/api/crawl/history")
    assert history.status_code == 200
    hist = history.json()
    assert hist["total"] >= 1
    entry = next(item for item in hist["items"] if item["run_id"] == run_id)
    assert entry["status"] == CrawlStatus.COMPLETED.value
    assert entry["pages_stored"] == 3
    assert entry["error_count"] == 0


async def test_crawl_start_validates_url(client):
    response = await client.post("/api/crawl", json={"url": "ftp://nope"})
    assert response.status_code == 422


async def test_unknown_run_returns_404(client):
    assert (await client.get("/api/crawl/missing")).status_code == 404
    assert (await client.get("/api/crawl/missing/pages")).status_code == 404
    assert (await client.delete("/api/crawl/missing")).status_code == 404
