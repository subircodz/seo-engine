"""Port: orchestrated site crawling (frontier, dedupe, robots, politeness)."""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol, runtime_checkable

from sie.domain.models.crawl import CrawlPolicy, CrawlStats, CrawlTarget
from sie.domain.models.page import FetchedPage


@runtime_checkable
class Crawler(Protocol):
    """Streams pages discovered from seed URLs, respecting the given policy.

    Contract:
    * Yields every visited page exactly once, including non-OK statuses.
    * Enforces ``CrawlPolicy``: page/depth caps, host scope, robots.txt,
      per-host pacing and concurrency limits.
    * Deterministic and LLM-free; rendering strategy remains behind the
      ``Fetcher``/``Renderer`` ports.
    * Transport-level fetch failures are skipped and counted in
      ``get_crawl_stats`` rather than aborting the run.
    """

    def crawl(self, target: CrawlTarget, policy: CrawlPolicy) -> AsyncIterator[FetchedPage]:
        """Validate and start a crawl; returns a lazy page stream.

        Raises ``CrawlAlreadyRunningError`` / ``InvalidCrawlTargetError``
        synchronously (before iteration begins).
        """
        ...

    def add_targets(self, targets: Sequence[CrawlTarget]) -> None:
        """Queue extra seeds into the active crawl's frontier.

        Raises ``CrawlNotRunningError`` when no crawl is in progress.
        """
        ...

    def get_crawl_stats(self) -> CrawlStats | None:
        """Snapshot for the active (or most recent) crawl; ``None`` if never run."""
        ...
