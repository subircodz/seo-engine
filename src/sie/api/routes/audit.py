"""Audit API endpoints — technical SEO + link graph."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field

from sie.domain.models.audit import AuditFinding, SiteArchitectureReport, TechnicalAuditResult

router = APIRouter(prefix="/api/audit", tags=["audit"])


# ── request / response models ───────────────────────────────────────────────


class TechnicalAuditRequest(BaseModel):
    run_id: str
    priorities: list[str] = Field(default_factory=lambda: ["P0", "P1", "P2"])


class TechnicalAuditResponse(BaseModel):
    run_id: str
    status: str
    total_pages: int
    total_issues: int
    critical_issues: int
    warning_issues: int
    info_issues: int
    summary_by_rule: dict[str, int]
    top_offending_pages: list[str]


class AuditFindingResponse(BaseModel):
    rule_code: str
    page_url: str
    severity: str
    message: str
    recommendation: str
    affected_elements: list[str]


class AuditFindingsListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditFindingResponse]


class LinkGraphRequest(BaseModel):
    run_id: str


class LinkNodeResponse(BaseModel):
    url: str
    depth: int
    incoming_count: int
    outgoing_count: int
    pagerank: float


class LinkGraphResponse(BaseModel):
    run_id: str
    total_pages: int
    total_internal_links: int
    avg_links_per_page: float
    orphans: list[str]
    dead_ends: list[str]
    max_depth: int
    avg_depth: float
    depth_distribution: dict[str, int]
    pagerank_top_10: list[str]
    pagerank_bottom_10: list[str]
    thin_connection_pages: list[str]
    link_velocity: dict


# ── helpers ─────────────────────────────────────────────────────────────────


def _audit_service(request: Request):
    return request.app.state.audit_service


def _crawled_pages(request: Request):
    return request.app.state.crawled_pages


def _result_to_response(run_id: str, result: TechnicalAuditResult) -> TechnicalAuditResponse:
    return TechnicalAuditResponse(
        run_id=run_id,
        status="completed",
        total_pages=result.total_pages,
        total_issues=result.total_issues,
        critical_issues=result.critical_count,
        warning_issues=result.warning_count,
        info_issues=result.info_count,
        summary_by_rule=result.summary_by_rule,
        top_offending_pages=list(result.top_offending_pages),
    )


def _finding_to_response(f: AuditFinding) -> AuditFindingResponse:
    return AuditFindingResponse(
        rule_code=f.rule_code,
        page_url=f.page_url,
        severity=f.severity,
        message=f.message,
        recommendation=f.recommendation,
        affected_elements=list(f.affected_elements),
    )


def _arch_to_response(run_id: str, r: SiteArchitectureReport) -> LinkGraphResponse:
    return LinkGraphResponse(
        run_id=run_id,
        total_pages=r.total_pages,
        total_internal_links=r.total_internal_links,
        avg_links_per_page=r.avg_links_per_page,
        orphans=list(r.orphans),
        dead_ends=list(r.dead_ends),
        max_depth=r.max_depth,
        avg_depth=r.avg_depth,
        depth_distribution=r.depth_distribution,
        pagerank_top_10=list(r.pagerank_top_10),
        pagerank_bottom_10=list(r.pagerank_bottom_10),
        thin_connection_pages=list(r.thin_connection_pages),
        link_velocity=asdict(r.link_velocity),
    )


# ── Technical SEO ───────────────────────────────────────────────────────────


@router.post("/technical", status_code=status.HTTP_200_OK, response_model=TechnicalAuditResponse)
async def run_technical_audit(body: TechnicalAuditRequest, request: Request):
    svc = _audit_service(request)
    pages = _crawled_pages(request).get(body.run_id)
    if pages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl run not found")
    priorities = set(body.priorities)
    result = await svc.run_technical_audit(body.run_id, pages, priorities=priorities)
    return _result_to_response(body.run_id, result)


@router.get("/technical/{run_id}", response_model=TechnicalAuditResponse)
async def get_technical_audit(run_id: str, request: Request):
    result = _audit_service(request).get_technical_result(run_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit not found")
    return _result_to_response(run_id, result)


@router.get("/technical/{run_id}/findings", response_model=AuditFindingsListResponse)
async def get_technical_findings(
    run_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    result = _audit_service(request).get_technical_result(run_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit not found")
    total = len(result.findings)
    page = result.findings[offset : offset + limit]
    return AuditFindingsListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_finding_to_response(f) for f in page],
    )


# ── Link graph ──────────────────────────────────────────────────────────────


@router.post("/link-graph", status_code=status.HTTP_200_OK, response_model=LinkGraphResponse)
async def run_link_graph(body: LinkGraphRequest, request: Request):
    svc = _audit_service(request)
    pages = _crawled_pages(request).get(body.run_id)
    if pages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl run not found")
    cfg = request.app.state.settings.audit
    report = await svc.run_link_graph(
        body.run_id,
        pages,
        max_depth=cfg.max_depth_for_link_analysis,
        damping=cfg.pagerank_damping,
        max_iterations=cfg.max_iterations,
        thin_threshold=cfg.threshold_thin_page,
    )
    return _arch_to_response(body.run_id, report)


@router.get("/link-graph/{run_id}", response_model=LinkGraphResponse)
async def get_link_graph(run_id: str, request: Request):
    report = _audit_service(request).get_architecture_report(run_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link graph not found")
    return _arch_to_response(run_id, report)


@router.get("/link-graph/{run_id}/orphan")
async def get_orphan_pages(run_id: str, request: Request):
    report = _audit_service(request).get_architecture_report(run_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link graph not found")
    return {"run_id": run_id, "orphans": list(report.orphans), "count": len(report.orphans)}


@router.get("/link-graph/{run_id}/depth")
async def get_depth_analysis(run_id: str, request: Request):
    report = _audit_service(request).get_architecture_report(run_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link graph not found")
    return {
        "run_id": run_id,
        "max_depth": report.max_depth,
        "avg_depth": report.avg_depth,
        "depth_distribution": report.depth_distribution,
    }
