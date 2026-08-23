"""Domain events emitted during crawl execution."""

from dataclasses import dataclass

from sie.domain.models.crawl import CrawlStatus


@dataclass(frozen=True, slots=True)
class PageFetchCompleted:
    run_id: str
    url: str
    status_code: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ErrorOccurred:
    run_id: str
    url: str
    reason: str


@dataclass(frozen=True, slots=True)
class CrawlFinished:
    run_id: str
    status: CrawlStatus
    pages_stored: int


CrawlEvent = PageFetchCompleted | ErrorOccurred | CrawlFinished
