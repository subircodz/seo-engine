"""Domain models (immutable value objects)."""

from sie.domain.models.crawl import (
    CrawlPageRecord,
    CrawlPolicy,
    CrawlRunRecord,
    CrawlStats,
    CrawlStatus,
    CrawlTarget,
)
from sie.domain.models.events import CrawlEvent, CrawlFinished, ErrorOccurred, PageFetchCompleted
from sie.domain.models.page import FetchedPage, RenderedPage

__all__ = [
    "CrawlEvent",
    "CrawlFinished",
    "CrawlPageRecord",
    "CrawlPolicy",
    "CrawlRunRecord",
    "CrawlStats",
    "CrawlStatus",
    "CrawlTarget",
    "ErrorOccurred",
    "FetchedPage",
    "PageFetchCompleted",
    "RenderedPage",
]
