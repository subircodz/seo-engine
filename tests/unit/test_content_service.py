"""Unit tests for Content Service."""

from __future__ import annotations

import pytest

from sie.domain.models.audit import PageDOM, PageImage
from sie.domain.models.content import (
    ContentAnalysisConfig,
    ContentType,
    QualityTier,
)
from sie.domain.models.page import FetchedPage
from sie.domain.ports.parsing import PageParser
from sie.domain.ports.persistence import CrawlRunRepository
from sie.domain.services.content_service import ContentService


class MockParser(PageParser):
    def __init__(self):
        self.pages = {}

    def parse_page(self, page: FetchedPage) -> PageDOM:
        return PageDOM(
            url=page.url,
            status_code=page.status_code,
            title="Test Title",
            meta_description="Test Description",
            h1s=("H1 Content",),
            h2s=("H2 Content",),
            images=(PageImage(src="/img.jpg", alt="Alt Text"),),
            internal_links=("https://example.com/internal",),
            external_links=("https://other.com/external",),
            jsonld_types=("Article",),
        )

    def parse_links(self, page: FetchedPage):
        from sie.domain.models.audit import ExtractedLink, LinkExtraction

        return LinkExtraction(
            source_url=page.url,
            links=(
                ExtractedLink(
                    target_url="https://example.com/internal",
                    anchor_text="Internal",
                    is_internal=True,
                ),
                ExtractedLink(
                    target_url="https://other.com/external",
                    anchor_text="External",
                    is_internal=False,
                ),
            ),
        )


class MockRepository(CrawlRunRepository):
    def __init__(self):
        self.metrics = {}
        self.comparisons = {}
        self.reports = {}

    async def create_run(self, run):
        pass

    async def finish_run(
        self, run_id, *, status, completed_at, error=None, total_pages=0, error_count=0
    ):
        pass

    async def get_run(self, run_id):
        return None

    async def add_page(self, run_id, page):
        pass

    async def list_pages(self, run_id, *, limit, offset):
        return 0, []

    async def list_runs(self, *, limit=50, offset=0):
        return 0, []

    async def save_content_metrics(self, run_id, metrics):
        self.metrics[run_id] = metrics

    async def get_content_metrics(self, run_id):
        return self.metrics.get(run_id, [])

    async def save_content_comparisons(self, run_id, comparisons):
        self.comparisons[run_id] = comparisons

    async def get_content_comparisons(self, run_id):
        return self.comparisons.get(run_id, [])

    async def save_quality_report(self, run_id, report):
        self.reports[run_id] = report

    async def get_quality_report(self, run_id):
        return self.reports.get(run_id)


@pytest.fixture
def mock_repo():
    return MockRepository()


@pytest.fixture
def mock_parser():
    return MockParser()


@pytest.fixture
def content_service(mock_repo, mock_parser):
    return ContentService(mock_repo, mock_parser)


@pytest.fixture
def sample_pages():
    return [
        FetchedPage(
            url="https://example.com/page1",
            final_url="https://example.com/page1",
            status_code=200,
            headers={},
            content=b"<html><body><h1>Test</h1><p>Content one</p></body></html>",
            content_type="text/html",
            depth=0,
        ),
        FetchedPage(
            url="https://example.com/page2",
            final_url="https://example.com/page2",
            status_code=200,
            headers={},
            content=b"<html><body><h1>Test</h1><p>Content two</p></body></html>",
            content_type="text/html",
            depth=1,
        ),
    ]


@pytest.mark.asyncio
async def test_analyze_content(content_service, sample_pages):
    config = ContentAnalysisConfig()
    metrics = await content_service.analyze_content("run1", sample_pages, config)

    assert len(metrics) == 2
    assert metrics[0].url == "https://example.com/page1"
    assert metrics[1].url == "https://example.com/page2"
    assert metrics[0].word_count > 0
    assert metrics[0].content_type in ContentType


@pytest.mark.asyncio
async def test_analyze_content_cached(content_service, sample_pages):
    config = ContentAnalysisConfig()
    await content_service.analyze_content("run1", sample_pages, config)
    metrics2 = content_service.get_analysis("run1")

    assert metrics2 is not None
    assert len(metrics2) == 2


@pytest.mark.asyncio
async def test_run_comparison(content_service, sample_pages):
    config = ContentAnalysisConfig()
    metrics = await content_service.analyze_content("run1", sample_pages, config)
    comparisons = await content_service.run_comparison("run1", metrics, config)

    assert isinstance(comparisons, list)


@pytest.mark.asyncio
async def test_run_comparison_single_page(content_service, sample_pages):
    config = ContentAnalysisConfig()
    # Only one page
    metrics = await content_service.analyze_content("run1", [sample_pages[0]], config)
    comparisons = await content_service.run_comparison("run1", metrics, config)

    assert comparisons == []


@pytest.mark.asyncio
async def test_generate_quality_report(content_service, sample_pages):
    config = ContentAnalysisConfig()
    metrics = await content_service.analyze_content("run1", sample_pages, config)
    report = await content_service.generate_quality_report("run1", metrics)

    assert report.run_id == "run1"
    assert report.total_pages == 2
    assert report.analyzed_pages == 2
    assert isinstance(report.avg_quality_score, float)
    assert all(t in report.quality_distribution for t in QualityTier)


@pytest.mark.asyncio
async def test_generate_quality_report_empty(content_service):
    report = await content_service.generate_quality_report("run1", [])

    assert report.total_pages == 0
    assert report.avg_quality_score == 0.0
    assert report.thin_content_pages == ()


@pytest.mark.asyncio
async def test_get_page_metrics(content_service, sample_pages):
    config = ContentAnalysisConfig()
    await content_service.analyze_content("run1", sample_pages, config)
    metrics = await content_service.get_page_metrics("run1", "https://example.com/page1")

    assert metrics is not None
    assert metrics.url == "https://example.com/page1"


@pytest.mark.asyncio
async def test_get_page_metrics_not_found(content_service, sample_pages):
    config = ContentAnalysisConfig()
    await content_service.analyze_content("run1", sample_pages, config)
    metrics = await content_service.get_page_metrics("run1", "https://example.com/nonexistent")

    assert metrics is None


@pytest.mark.asyncio
async def test_get_pages_by_type(content_service, sample_pages):
    config = ContentAnalysisConfig()
    await content_service.analyze_content("run1", sample_pages, config)
    pages = await content_service.get_pages_by_type("run1", "article")

    assert isinstance(pages, list)


@pytest.mark.asyncio
async def test_get_pages_by_quality(content_service, sample_pages):
    config = ContentAnalysisConfig()
    await content_service.analyze_content("run1", sample_pages, config)
    pages = await content_service.get_pages_by_quality("run1", QualityTier.GOOD)

    assert isinstance(pages, list)


def test_build_html_map(content_service, sample_pages):
    html_map = content_service._build_html_map(sample_pages)

    assert len(html_map) == 2
    assert "https://example.com/page1" in html_map
    assert "https://example.com/page2" in html_map
    assert "<h1>Test</h1>" in html_map["https://example.com/page1"]
