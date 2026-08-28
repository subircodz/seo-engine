"""Durable background job API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from sie.api.auth import api_key_auth
from sie.infrastructure.jobs.durable_queue import JobNotFoundError

router = APIRouter(
    prefix="/api/jobs",
    tags=["jobs"],
    dependencies=[Depends(api_key_auth)],
)


class SiteAnalysisJobRequest(BaseModel):
    """Parameters accepted by the durable site-analysis worker."""

    domain: str = Field(..., min_length=1)
    max_pages: int = Field(default=100, ge=1, le=5000)
    max_keywords: int = Field(default=50, ge=1, le=500)
    country: str = Field(default="us", min_length=2, max_length=2)
    target_countries: list[str] = Field(default_factory=list, max_length=10)
    device: str = Field(default="desktop")
    competitors: list[str] = Field(default_factory=list, max_length=20)
    deep_aio: bool = True
    deep_geo: bool = True


@router.post("/site-analysis", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_site_analysis(
    payload: SiteAnalysisJobRequest, request: Request
) -> dict[str, Any]:
    """Queue a site analysis without blocking the HTTP request."""
    queue = request.app.state.job_queue
    job_id = await queue.enqueue("site-analysis", payload.model_dump())
    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}")
async def get_job(job_id: str, request: Request) -> dict[str, Any]:
    """Return durable job status/result."""
    try:
        return await request.app.state.job_queue.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
