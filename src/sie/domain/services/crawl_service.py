"""Application service orchestrating crawl run lifecycles.

Depends exclusively on the ``Crawler`` and ``CrawlRunRepository`` ports, so it
stays framework- and storage-agnostic (and testable with in-memory fakes).
"""

import asyncio
import inspect
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import aclosing
from dataclasses import asdict
from datetime import UTC, datetime

from sie.domain.errors import CrawlAlreadyRunningError
from sie.domain.models.crawl import (
    CrawlPageRecord,
    CrawlPolicy,
    CrawlRunRecord,
    CrawlStats,
    CrawlStatus,
    CrawlTarget,
)
from sie.domain.models.events import CrawlEvent, CrawlFinished, ErrorOccurred, PageFetchCompleted
from sie.domain.models.page import FetchedPage
from sie.domain.ports.crawling import Crawler
from sie.domain.ports.persistence import CrawlRunRepository
from sie.logging import get_logger

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class CrawlService:
    """Owns run identity, persistence boundaries, events and cooperative abort."""

    def __init__(
        self,
        crawler: Crawler,
        repository: CrawlRunRepository,
        handlers: Sequence[Callable[[CrawlEvent], Awaitable[None]]] = (),
        pages_store: dict[str, list[FetchedPage]] | None = None,
    ) -> None:
        self._crawler = crawler
        self._repository = repository
        self._handlers: list[Callable[[CrawlEvent], Awaitable[None]]] = list(handlers)
        self._pages_store = pages_store or {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._stops: dict[str, asyncio.Event] = {}
        self._active_run_id: str | None = None
        self._start_lock = asyncio.Lock()

    def subscribe(self, handler: Callable[[CrawlEvent], Awaitable[None]]) -> None:
        self._handlers.append(handler)

    async def start_run(self, target: CrawlTarget, policy: CrawlPolicy) -> str:
        """Create a persisted run and start crawling in the background.

        Raises ``CrawlAlreadyRunningError`` / ``InvalidCrawlTargetError``
        before any state is written.
        """
        stream = self._crawler.crawl(target, policy)

        async with self._start_lock:
            if any(not task.done() for task in self._tasks.values()):
                raise CrawlAlreadyRunningError("another crawl is already running")
            run_id = uuid.uuid4().hex
            await self._repository.create_run(
                CrawlRunRecord(
                    id=run_id,
                    target_url=target.seed_url,
                    status=CrawlStatus.RUNNING,
                    started_at=_now(),
                    policy_snapshot=asdict(policy),
                )
            )
            stop = asyncio.Event()
            self._stops[run_id] = stop
            self._active_run_id = run_id
            self._tasks[run_id] = asyncio.create_task(
                self._execute(run_id, stream, target.seed_url, stop)
            )
        return run_id

    async def abort(self, run_id: str) -> str:
        """Request cooperative abort. Returns one of:
        ``not_found``, ``abort_requested``, ``already_finished``."""
        stop = self._stops.get(run_id)
        if stop is not None:
            stop.set()
            return "abort_requested"

        run = await self._repository.get_run(run_id)
        if run is None:
            return "not_found"
        if run.status in (CrawlStatus.COMPLETED, CrawlStatus.ABORTED, CrawlStatus.FAILED):
            return "already_finished"
        return "abort_requested"

    async def get_run(self, run_id: str) -> tuple[CrawlRunRecord, int] | None:
        """Return ``(run_record, pages_stored)`` or ``None`` when unknown."""
        run = await self._repository.get_run(run_id)
        if run is None:
            return None
        total, _ = await self._repository.list_pages(run_id, limit=1, offset=0)
        return run, total

    async def live_stats(self, run_id: str) -> CrawlStats | None:
        if self._active_run_id == run_id:
            stats = self._crawler.get_crawl_stats()
            if stats is not None:
                return stats
        # Not active (finished, aborted, or engine already released): reconstruct
        # the final snapshot from persisted state so polling stays informative.
        run = await self._repository.get_run(run_id)
        if run is None:
            return None
        return CrawlStats(
            status=run.status,
            pages_discovered=run.total_pages,
            pages_fetched=run.total_pages,
            transport_errors=0,
            robots_skipped=0,
            frontier_size=0,
            started_at=run.started_at,
            finished_at=run.completed_at,
        )

    async def list_pages(
        self, run_id: str, *, limit: int, offset: int
    ) -> tuple[int, list[CrawlPageRecord]] | None:
        if await self._repository.get_run(run_id) is None:
            return None
        return await self._repository.list_pages(run_id, limit=limit, offset=offset)

    async def list_runs(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[int, list[CrawlRunRecord]]:
        return await self._repository.list_runs(limit=limit, offset=offset)

    async def shutdown(self, timeout: float = 10.0) -> None:
        for stop in self._stops.values():
            stop.set()
        if not self._tasks:
            return
        _, pending = await asyncio.wait(set(self._tasks.values()), timeout=timeout)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _execute(
        self,
        run_id: str,
        stream: AsyncIterator[FetchedPage],
        seed_url: str,
        stop: asyncio.Event,
    ) -> None:
        final_status = CrawlStatus.COMPLETED
        error: str | None = None
        stored = 0
        errors = 0
        run_pages: list[FetchedPage] = []
        try:
            async with aclosing(stream) as pages:
                async for page in pages:
                    if stop.is_set():
                        final_status = CrawlStatus.ABORTED
                        break
                    run_pages.append(page)
                    await self._repository.add_page(
                        run_id,
                        CrawlPageRecord(
                            url=page.url,
                            status_code=page.status_code,
                            fetched_at=page.fetched_at,
                            html_size=len(page.content),
                            html_content=page.content,
                            content_type=page.content_type,
                            depth=page.depth,
                            parent_url=page.parent_url,
                        ),
                    )
                    stored += 1
                    if page.ok:
                        await self._emit(
                            PageFetchCompleted(
                                run_id=run_id,
                                url=page.url,
                                status_code=page.status_code,
                                duration_ms=page.duration_ms,
                            )
                        )
                    else:
                        errors += 1
                        await self._emit(
                            ErrorOccurred(
                                run_id=run_id, url=page.url, reason=f"http_{page.status_code}"
                            )
                        )
        except Exception as exc:
            logger.exception("crawl run %s failed", run_id)
            final_status = CrawlStatus.FAILED
            error = f"{type(exc).__name__}: {exc}"
            await self._emit(ErrorOccurred(run_id=run_id, url=seed_url, reason=error))
        finally:
            self._pages_store[run_id] = run_pages
            await self._repository.finish_run(
                run_id,
                status=final_status,
                completed_at=_now(),
                error=error,
                total_pages=stored,
                error_count=errors,
            )
            await self._emit(CrawlFinished(run_id=run_id, status=final_status, pages_stored=stored))
            self._tasks.pop(run_id, None)
            self._stops.pop(run_id, None)
            if self._active_run_id == run_id:
                self._active_run_id = None

    async def _emit(self, event: CrawlEvent) -> None:
        for handler in self._handlers:
            try:
                result = handler(event)
                if inspect.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("crawl event handler failed for %s", event)
