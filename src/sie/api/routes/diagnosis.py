"""Diagnosis API endpoints — structured SEO diagnosis."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field

from sie.api.auth import api_key_auth
from sie.domain.models.diagnosis import (
    DiagnosisEvidence,
    DiagnosisIssue,
    DiagnosisResult,
)

router = APIRouter(
    prefix="/api/diagnosis",
    tags=["diagnosis"],
    dependencies=[Depends(api_key_auth)],
)


# ── request / response models ───────────────────────────────────────────────


class DiagnosisRequest(BaseModel):
    run_id: str
    priorities: list[str] = Field(default_factory=lambda: ["P0", "P1", "P2", "P3"])


class DiagnosisEvidenceResponse(BaseModel):
    metric_name: str
    metric_value: float | int | str | bool | None = None
    threshold: float | int | None = None
    description: str = ""
    source_url: str = ""


class DiagnosisIssueResponse(BaseModel):
    rule_code: str
    category: str
    severity: str
    priority: str
    affected_url: str
    explanation: str
    recommendation: str
    evidence: list[DiagnosisEvidenceResponse]
    confidence: float
    source_engine: str


class DiagnosisResponse(BaseModel):
    run_id: str
    status: str
    total_issues: int
    issues_by_priority: dict[str, int]
    issues_by_severity: dict[str, int]
    issues_by_category: dict[str, int]
    top_affected_pages: list[str]


class DiagnosisIssuesListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DiagnosisIssueResponse]


# ── helpers ─────────────────────────────────────────────────────────────────


def _diagnosis_service(request: Request):
    return request.app.state.diagnosis_service


def _crawled_pages(request: Request):
    return request.app.state.crawled_pages


def _evidence_to_response(e: DiagnosisEvidence) -> DiagnosisEvidenceResponse:
    return DiagnosisEvidenceResponse(
        metric_name=e.metric_name,
        metric_value=e.metric_value,
        threshold=e.threshold,
        description=e.description,
        source_url=e.source_url,
    )


def _issue_to_response(i: DiagnosisIssue) -> DiagnosisIssueResponse:
    return DiagnosisIssueResponse(
        rule_code=i.rule_code,
        category=i.category.value,
        severity=i.severity.value,
        priority=i.priority.value,
        affected_url=i.affected_url,
        explanation=i.explanation,
        recommendation=i.recommendation,
        evidence=[_evidence_to_response(e) for e in i.evidence],
        confidence=i.confidence,
        source_engine=i.source_engine,
    )


def _result_to_response(run_id: str, result: DiagnosisResult) -> DiagnosisResponse:
    return DiagnosisResponse(
        run_id=run_id,
        status="completed",
        total_issues=result.total_issues,
        issues_by_priority=result.issues_by_priority,
        issues_by_severity=result.issues_by_severity,
        issues_by_category=result.issues_by_category,
        top_affected_pages=list(result.top_affected_pages),
    )


# ── Diagnosis ───────────────────────────────────────────────────────────────


@router.post("/run", status_code=status.HTTP_200_OK, response_model=DiagnosisResponse)
async def run_diagnosis_endpoint(body: DiagnosisRequest, request: Request):
    svc = _diagnosis_service(request)
    pages = _crawled_pages(request).get(body.run_id)
    if pages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl run not found")
    priorities = set(body.priorities)
    result = await svc.run_diagnosis(body.run_id, pages, priorities=priorities)
    return _result_to_response(body.run_id, result)


@router.get("/{run_id}", response_model=DiagnosisResponse)
async def get_diagnosis(run_id: str, request: Request):
    result = _diagnosis_service(request).get_result(run_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="diagnosis not found")
    return _result_to_response(run_id, result)


@router.get("/{run_id}/issues", response_model=DiagnosisIssuesListResponse)
async def get_diagnosis_issues(
    run_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    severity: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    result = _diagnosis_service(request).get_result(run_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="diagnosis not found")

    issues = list(result.issues)

    if severity:
        issues = [i for i in issues if i.severity.value == severity]
    if priority:
        issues = [i for i in issues if i.priority.value == priority]
    if category:
        issues = [i for i in issues if i.category.value == category]

    total = len(issues)
    page = issues[offset : offset + limit]
    return DiagnosisIssuesListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_issue_to_response(i) for i in page],
    )
