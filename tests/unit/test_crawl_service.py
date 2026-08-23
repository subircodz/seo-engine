"""CrawlService lifecycle, abort and event emission (unit, in-memory)."""

import asyncio

import pytest

from sie.domain.errors import CrawlAlreadyRunningError
from sie.domain.models.crawl import CrawlPolicy, CrawlStatus, CrawlTarget
from sie.domain.models.events import CrawlFinished, ErrorOccurred, PageFetchCompleted
from sie.domain.models.page import FetchedPage
from sie.domain.services.crawl_service import CrawlService
from tests.fakes import FailingCrawler, FakeCrawler, InMemoryCrawlRunRepository


def _page(url: str = "https://example.com/", status: int = 200) -> FetchedPage:
    return FetchedPage(url=url, final_url=url, status_code=status, headers={}, content=b"ok")


ERROR_PAGE = FetchedPage(
    url="https://example.com/bad",
    final_url="https://example.com/bad",
    status_code=500,
    headers={},
    content=b"err",
)

POLICY = CrawlPolicy(max_pages=100, depth_limit=3)
TARGET = CrawlTarget(seed_url="https://example.com/")
MEANWHILE_TARGET = CrawlTarget(seed_url="https://example.com/other")
MEANWHILE_POLICY = CrawlPolicy(max_pages=5, depth_limit=1)


def _svc(crawler, handlers=()):
    return CrawlService(crawler, InMemoryCrawlRunRepository(), handlers=list(handlers))


async def _wait_terminal(service: CrawlService, run_id: str, timeout: float = 2.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        result = await service.get_run(run_id)
        if result is not None and result[0].status.value in ("completed", "aborted", "failed"):
            return result[0]
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not reach terminal status within {timeout}s")


async def test_start_run_returns_id():
    svc = _svc(FakeCrawler([_page()]))
    run_id = await svc.start_run(TARGET, POLICY)
    assert isinstance(run_id, str) and len(run_id) == 32


async def test_completed_run_persists_pages():
    events = []

    async def capture(event):
        events.append(event)

    svc = _svc(
        FakeCrawler([_page("https://example.com/"), _page("https://example.com/a")]),
        handlers=[capture],
    )
    run_id = await svc.start_run(TARGET, POLICY)
    run = await _wait_terminal(svc, run_id)

    assert run.status == CrawlStatus.COMPLETED
    total, _ = await svc.list_pages(run_id, limit=10, offset=0)
    assert total == 2
    assert len([e for e in events if isinstance(e, PageFetchCompleted)]) == 2
    assert any(isinstance(e, CrawlFinished) and e.pages_stored == 2 for e in events)


async def test_error_page_emits_error_event():
    events = []

    async def capture(event):
        events.append(event)

    svc = _svc(FakeCrawler([ERROR_PAGE]), handlers=[capture])
    run_id = await svc.start_run(TARGET, POLICY)
    await _wait_terminal(svc, run_id)

    errs = [e for e in events if isinstance(e, ErrorOccurred)]
    assert len(errs) == 1
    assert errs[0].reason == "http_500"


async def test_already_running_raises():
    stall = asyncio.Event()
    svc = _svc(FakeCrawler([_page(), _page()], stall=stall))
    await svc.start_run(TARGET, POLICY)
    with pytest.raises(CrawlAlreadyRunningError):
        await svc.start_run(MEANWHILE_TARGET, MEANWHILE_POLICY)
    stall.set()
    await asyncio.sleep(0.05)


async def test_abort_sets_aborted():
    stall = asyncio.Event()
    svc = _svc(FakeCrawler([_page(), _page()], stall=stall))
    run_id = await svc.start_run(TARGET, POLICY)
    await asyncio.sleep(0.02)
    outcome = await svc.abort(run_id)
    assert outcome == "abort_requested"
    stall.set()
    run = await _wait_terminal(svc, run_id)
    assert run.status == CrawlStatus.ABORTED


async def test_abort_unknown_returns_not_found():
    svc = _svc(FakeCrawler())
    assert await svc.abort("nonexistent") == "not_found"


async def test_abort_completed_returns_already_finished():
    svc = _svc(FakeCrawler([_page()]))
    run_id = await svc.start_run(TARGET, POLICY)
    await _wait_terminal(svc, run_id)
    assert await svc.abort(run_id) == "already_finished"


async def test_crawler_failure_marks_failed():
    svc = _svc(FailingCrawler(RuntimeError("boom")))
    run_id = await svc.start_run(TARGET, POLICY)
    run = await _wait_terminal(svc, run_id)
    assert run.status == CrawlStatus.FAILED
    assert "boom" in (run.error or "")
