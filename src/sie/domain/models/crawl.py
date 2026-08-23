"""Crawl request/result models."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class CrawlStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CrawlTarget:
    """What to crawl: a seed URL (whole site, section, or single page)."""

    seed_url: str


@dataclass(frozen=True, slots=True)
class CrawlPolicy:
    """Boundaries a crawl must respect. Defaults are deliberately polite."""

    max_pages: int = 1000
    depth_limit: int = 5
    respect_robots_txt: bool = True
    follow_cross_origin: bool = False
    rate_limit_per_host: float = 1.0


@dataclass(frozen=True, slots=True)
class CrawlStats:
    """Live snapshot of crawler progress for one run."""

    status: CrawlStatus
    pages_discovered: int
    pages_fetched: int
    transport_errors: int
    robots_skipped: int
    frontier_size: int
    started_at: datetime
    finished_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CrawlRunRecord:
    """Persisted state of one crawl run."""

    id: str
    target_url: str
    status: CrawlStatus
    started_at: datetime
    completed_at: datetime | None = None
    policy_snapshot: Mapping[str, object] = field(default_factory=dict)
    error: str | None = None
    total_pages: int = 0
    error_count: int = 0


@dataclass(frozen=True, slots=True)
class CrawlPageRecord:
    """Persisted result of one fetched page within a run."""

    url: str
    status_code: int | None = None
    fetched_at: datetime | None = None
    html_size: int | None = None
    error_message: str | None = None
    content_type: str | None = None
    depth: int = 0
    parent_url: str | None = None
