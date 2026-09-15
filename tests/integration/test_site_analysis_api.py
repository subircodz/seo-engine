"""Black-box acceptance test for the complete site-analysis HTTP workflow."""

from sie.domain.models.page import FetchedPage
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.services.evidence_aware_site_analysis import EvidenceAwareSiteAnalysisService
from sie.domain.services.site_analysis import create_site_analysis_service
from sie.infrastructure.search.mock_provider import MockSearchProvider
from tests.fakes import FakeCrawler


SITE_HOME = b"""
<!doctype html>
<html>
<head>
  <title>Acme Analytics Platform</title>
  <meta name="description"
        content="Acme provides analytics dashboards and reporting software for growing teams.">
</head>
<body>
  <h1>Analytics Platform</h1>
  <p>Acme Analytics Platform helps growing teams build analytics dashboards, reporting workflows,
  data monitoring, business intelligence views, and operational reports from reliable business
  data.</p>
  <p>Our reporting software connects business data to practical dashboards for teams that need
  analytics, reporting, monitoring, and clear operational visibility every day.</p>
  <a href="/reports">Reporting</a>
</body>
</html>
"""

SITE_REPORTS = b"""
<!doctype html>
<html>
<head>
  <title>Acme Reporting Software</title>
  <meta name="description"
        content="Reporting software and dashboards from Acme Analytics Platform.">
</head>
<body>
  <h1>Reporting Software</h1>
  <p>Acme reporting software turns business data into dashboards, operational reports,
  analytics views, and useful reporting workflows for teams.</p>
  <a href="/">Analytics Platform</a>
</body>
</html>
"""


def _inject_site_analysis_service(harness, search_provider):
    """Rebuild only the application service so the real HTTP path uses test providers."""
    raw = create_site_analysis_service(
        crawl_service=harness.app.state.crawl_service,
        audit_service=harness.app.state.audit_service,
        content_service=harness.app.state.content_service,
        search_provider=search_provider,
        repository=harness.app.state.repository,
        crux_service=harness.app.state.crux_service,
    )
    harness.app.state.site_analysis_service = EvidenceAwareSiteAnalysisService(raw)


def _inject_crawler(harness):
    pages = [
        FetchedPage(
            url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=SITE_HOME,
            content_type="text/html; charset=utf-8",
            depth=0,
            parent_url=None,
        ),
        FetchedPage(
            url="https://example.com/reports",
            final_url="https://example.com/reports",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=SITE_REPORTS,
            content_type="text/html; charset=utf-8",
            depth=1,
            parent_url="https://example.com/",
        ),
    ]
    harness.app.state.crawl_service._crawler = FakeCrawler(pages)


async def test_site_analysis_black_box_http_workflow(harness):
    """POST the public API, execute the real orchestration, and validate its response."""
    search_provider = MockSearchProvider(
        results={
            "analytics platform": SearchResult(
                keyword="analytics platform",
                items=(
                    SearchResultItem(
                        position=1,
                        title="Acme Analytics Platform",
                        url="https://example.com/",
                    ),
                ),
            )
        }
    )
    _inject_crawler(harness)
    _inject_site_analysis_service(harness, search_provider)

    response = await harness.client.post(
        "/api/site/analyze",
        json={
            "domain": "https://example.com",
            "max_pages": 5,
            "max_keywords": 1,
            "country": "us",
            "target_countries": [],
            "device": "desktop",
            "competitors": [],
            "deep_aio": False,
            "deep_geo": False,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["domain"] == "example.com"
    assert body["crawl_run_id"]
    assert 0 <= body["overall_score"] <= 100
    assert 0 <= body["technical_score"] <= 100
    assert 0 <= body["content_score"] <= 100
    assert 0 <= body["ranking_score"] <= 100
    assert 0 <= body["architecture_score"] <= 100
    assert body["technical"]["pages_crawled"] == 2
    assert body["content"]["pages_analyzed"] == 2
    assert body["architecture"]["total_pages"] == 2
    assert body["rankings"] is not None
    assert body["rankings"]["domain"] == "example.com"
    assert body["recommendations"] is not None
    assert body["report_metadata"]["target_url"] == "https://example.com"
    assert body["access_status"]["accessible"] is True
    assert body["access_status"]["analysis_status"] == "SUCCESS"

    persisted = await harness.client.get(f"/api/crawl/{body['crawl_run_id']}")
    assert persisted.status_code == 200
    assert persisted.json()["status"] == "completed"
    assert persisted.json()["pages_stored"] == 2
