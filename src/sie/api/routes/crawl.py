"""Crawl management API."""

from dataclasses import asdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field

from sie.domain.errors import CrawlAlreadyRunningError, InvalidCrawlTargetError
from sie.domain.models.crawl import CrawlPolicy, CrawlStatus, CrawlTarget
from sie.domain.services.crawl_service import CrawlService

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


class StartCrawlRequest(BaseModel):
    url: Annotated[str, Field(min_length=8, pattern=r"^https?://")]
    max_pages: Annotated[int | None, Field(default=None, ge=1, le=100_000)] = None
    depth_limit: Annotated[int | None, Field(default=None, ge=0, le=50)] = None


class StartCrawlResponse(BaseModel):
    run_id: str
    status: str
    poll_url: str


class CrawlStatsResponse(BaseModel):
    status: str
    pages_discovered: int
    pages_fetched: int
    transport_errors: int
    robots_skipped: int
    frontier_size: int
    started_at: datetime
    completed_at: datetime | None = None


class CrawlRunResponse(BaseModel):
    run_id: str
    target_url: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None = None
    pages_stored: int
    stats: CrawlStatsResponse | None = None


class CrawlPageItem(BaseModel):
    url: str
    status_code: int | None
    fetched_at: datetime | None
    html_size: int | None
    error_message: str | None
    content_type: str | None = None
    depth: int | None = None
    parent_url: str | None = None


class CrawlPagesResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CrawlPageItem]


class CrawlRunSummary(BaseModel):
    run_id: str
    target_url: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    pages_stored: int
    error_count: int


class CrawlHistoryResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CrawlRunSummary]


def _service(request: Request) -> CrawlService:
    return request.app.state.crawl_service


def _policy_from_settings(request: Request, body: StartCrawlRequest) -> CrawlPolicy:
    cs = request.app.state.settings.crawler
    return CrawlPolicy(
        max_pages=body.max_pages if body.max_pages is not None else cs.max_pages,
        depth_limit=body.depth_limit if body.depth_limit is not None else cs.depth_limit,
        respect_robots_txt=cs.respect_robots_txt,
        follow_cross_origin=cs.follow_cross_origin,
        rate_limit_per_host=cs.rate_limit_per_host,
    )


@router.post("", response_model=StartCrawlResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_crawl(body: StartCrawlRequest, request: Request) -> StartCrawlResponse:
    svc = _service(request)
    target = CrawlTarget(seed_url=body.url)
    policy = _policy_from_settings(request, body)
    try:
        run_id = await svc.start_run(target, policy)
    except CrawlAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidCrawlTargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return StartCrawlResponse(
        run_id=run_id, status=CrawlStatus.RUNNING.value, poll_url=f"/api/crawl/{run_id}"
    )


@router.get("/history", response_model=CrawlHistoryResponse)
async def crawl_history(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CrawlHistoryResponse:
    total, runs = await _service(request).list_runs(limit=limit, offset=offset)
    return CrawlHistoryResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            CrawlRunSummary(
                run_id=r.id,
                target_url=r.target_url,
                status=r.status.value,
                started_at=r.started_at,
                completed_at=r.completed_at,
                pages_stored=r.total_pages,
                error_count=r.error_count,
            )
            for r in runs
        ],
    )


@router.get("/{run_id}", response_model=CrawlRunResponse)
async def get_crawl(run_id: str, request: Request) -> CrawlRunResponse:
    svc = _service(request)
    result = await svc.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    run, pages_stored = result
    live = await svc.live_stats(run_id)
    return CrawlRunResponse(
        run_id=run.id,
        target_url=run.target_url,
        status=run.status.value,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error=run.error,
        pages_stored=pages_stored,
        stats=CrawlStatsResponse(**asdict(live)) if live is not None else None,
    )


@router.get("/{run_id}/pages", response_model=CrawlPagesResponse)
async def list_crawl_pages(
    run_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CrawlPagesResponse:
    svc = _service(request)
    result = await svc.list_pages(run_id, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    total, items = result
    return CrawlPagesResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[CrawlPageItem(**asdict(item)) for item in items],
    )


@router.delete("/{run_id}", status_code=status.HTTP_200_OK)
async def abort_crawl(run_id: str, request: Request) -> dict:
    svc = _service(request)
    outcome = await svc.abort(run_id)
    if outcome == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    if outcome == "already_finished":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="run is already finished",
        )
    return {"run_id": run_id, "status": "abort_requested"}
