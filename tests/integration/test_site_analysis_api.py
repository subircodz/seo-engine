"""Black-box acceptance test for the complete site-analysis HTTP workflow."""

from sie.domain.models.page import FetchedPage
from sie.domain.models.search_aio import AIOCitation, AIOverviewObservation, AIOverviewType
from sie.domain.models.search_geo import (
    EntityMention,
    EntityType,
    GenerativeEngineType,
    GEOObservation,
)
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.services.evidence_aware_site_analysis import EvidenceAwareSiteAnalysisService
from sie.domain.services.site_analysis import create_site_analysis_service
from sie.infrastructure.search.mock_provider import MockSearchProvider
from sie.infrastructure.search.provider_registry import ProviderRegistry


class _FakeCrawler:
    """Deterministic crawler seam for the application-level acceptance test."""

    def __init__(self, pages):
        self._pages = list(pages)

    def crawl(self, target, policy):
        return self._stream()

    async def _stream(self):
        for page in self._pages:
            yield page

    def add_targets(self, targets):
        pass

    def get_crawl_stats(self):
        return None


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
    """Rebuild the real service with the test capability registry."""
    registry = ProviderRegistry(
        default=search_provider,
        rankings=search_provider,
        aio=search_provider,
        geo=search_provider,
    )
    harness.app.state.search_provider = registry
    raw = create_site_analysis_service(
        crawl_service=harness.app.state.crawl_service,
        audit_service=harness.app.state.audit_service,
        content_service=harness.app.state.content_service,
        search_provider=registry,
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
    harness.app.state.crawl_service._crawler = _FakeCrawler(pages)


async def test_site_analysis_black_box_http_workflow(harness):
    """POST the public API, execute the real orchestration, and validate its output."""
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
        },
        aio_observations={
            "analytics platform": AIOverviewObservation(
                keyword="analytics platform",
                ai_type=AIOverviewType.AI_OVERVIEW,
                present=True,
                target_cited=True,
                target_domain="example.com",
                citation_count=1,
                citations=(
                    AIOCitation(
                        domain="example.com",
                        url="https://example.com/",
                        position=1,
                        title="Acme Analytics Platform",
                    ),
                ),
                source="mock",
            )
        },
        geo_observations={
            ("analytics platform", GenerativeEngineType.CHATGPT): GEOObservation(
                keyword="analytics platform",
                engine_type=GenerativeEngineType.CHATGPT,
                target_mentioned=True,
                target_domain="example.com",
                mention_count=1,
                entity_mentions=(
                    EntityMention(
                        text="Acme Analytics Platform",
                        entity_type=EntityType.BRAND,
                        is_target=True,
                        domain="example.com",
                    ),
                ),
                source="mock",
            )
        },
    )
    _inject_crawler(harness)
    _inject_site_analysis_service(harness, search_provider)

    request_payload = {
        "domain": "https://example.com",
        "max_pages": 5,
        "max_keywords": 1,
        "country": "us",
        "target_countries": [],
        "device": "desktop",
        "competitors": [],
        "deep_aio": True,
        "deep_geo": True,
    }
    response = await harness.client.post("/api/site/analyze", json=request_payload)

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["domain"] == "example.com"
    assert body["crawl_run_id"]
    for score_name in (
        "overall_score",
        "technical_score",
        "content_score",
        "ranking_score",
        "architecture_score",
        "aio_score",
        "geo_score",
    ):
        assert 0 <= body[score_name] <= 100

    assert body["technical"]["pages_crawled"] == 2
    assert body["content"]["pages_analyzed"] == 2
    assert body["architecture"]["total_pages"] == 2
    assert body["rankings"]["domain"] == "example.com"
    assert body["rankings"]["total_keywords_tracked"] == 1
    assert body["aio"]["keywords_checked"] == 1
    assert body["aio"]["ai_overviews_present"] == 1
    assert body["aio"]["target_cited_count"] == 1
    assert body["geo"]["keywords_checked"] == 1
    assert body["geo"]["target_mentioned_count"] == 1
    assert body["geo"]["mention_rate"] == 1.0
    assert body["entity_analysis"]["entities_extracted"] > 0
    assert body["performance_summary"]["pages_analyzed"] == 2
    assert body["performance_summary"]["avg_html_size"] > 0
    assert body["search_opportunities"] is not None
    assert body["content_breakdown"] is not None
    assert body["ranking_breakdown"] is not None
    assert body["architecture_breakdown"] is not None
    assert body["aio_breakdown"] is not None
    assert body["geo_breakdown"] is not None
    assert body["recommendations"] is not None
    assert body["report_metadata"]["target_url"] == "https://example.com"
    assert body["access_status"]["accessible"] is True
    assert body["access_status"]["analysis_status"] == "SUCCESS"

    persisted = await harness.client.get(f"/api/crawl/{body['crawl_run_id']}")
    assert persisted.status_code == 200
    assert persisted.json()["status"] == "completed"
    assert persisted.json()["pages_stored"] == 2

    pdf_response = await harness.client.post("/api/site/analyze/pdf", json=request_payload)
    assert pdf_response.status_code == 200, pdf_response.text
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert pdf_response.content.startswith(b"%PDF-")
    assert len(pdf_response.content) > 1000
