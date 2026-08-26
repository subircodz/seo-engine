"""Intelligence API endpoints — LLM-powered SEO intelligence and action planning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

from sie.api.auth import api_key_auth

router = APIRouter(
    prefix="/api/intelligence",
    tags=["intelligence"],
    dependencies=[Depends(api_key_auth)],
)


# ── request / response models ───────────────────────────────────────────────


class IntelligenceRequest(BaseModel):
    run_id: str


class IntelligenceResponse(BaseModel):
    intelligence_id: str
    status: str
    summary: str
    top_issue_count: int
    action_count: int


class RootCauseResponse(BaseModel):
    title: str
    evidence: list[str]
    confidence: float


class TopIssueResponse(BaseModel):
    issue_code: str
    title: str
    interpretation: str
    impact: str
    confidence: float
    affected_url_count: int


class QuickWinResponse(BaseModel):
    action: str
    reason: str
    priority: str
    difficulty: str


class ActionPlanItemResponse(BaseModel):
    order: int
    action: str
    reason: str
    priority: str
    difficulty: str
    dependencies: list[str]


class IntelligenceDetailResponse(BaseModel):
    intelligence_id: str
    run_id: str
    status: str
    prompt_version: str
    model_name: str
    provider: str
    summary: str
    overall_assessment: str
    root_causes: list[RootCauseResponse]
    top_issues: list[TopIssueResponse]
    quick_wins: list[QuickWinResponse]
    action_plan: list[ActionPlanItemResponse]


class ActionPlanResponse(BaseModel):
    intelligence_id: str
    total_actions: int
    actions: list[ActionPlanItemResponse]


# ── helpers ─────────────────────────────────────────────────────────────────


def _intelligence_service(request: Request):
    return request.app.state.intelligence_service


def _diagnosis_service(request: Request):
    return request.app.state.diagnosis_service


def _crawled_pages(request: Request):
    return request.app.state.crawled_pages


def _repository(request: Request):
    return request.app.state.repository


# ── Intelligence endpoints ──────────────────────────────────────────────────


@router.post("/reason", status_code=status.HTTP_200_OK, response_model=IntelligenceResponse)
async def reason_intelligence(body: IntelligenceRequest, request: Request):
    """Run LLM-powered intelligence reasoning on a crawl run.

    Builds an evidence package from deterministic engine outputs, sends it
    to the LLM for reasoning, and persists the validated intelligence report.
    """
    svc = _intelligence_service(request)
    diag_svc = _diagnosis_service(request)
    pages = _crawled_pages(request).get(body.run_id)

    if pages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl run not found")

    # Get or compute diagnosis
    diagnosis = diag_svc.get_result(body.run_id)
    if diagnosis is None:
        diagnosis = await diag_svc.run_diagnosis(body.run_id, pages)

    # Build evidence package
    # Compute status distribution from crawled pages
    from collections import Counter

    from sie.domain.services.evidence_builder import build_evidence_package

    status_dist: dict[str, int] = dict(Counter(str(p.status_code) for p in pages))

    # Compute technical audit for evidence
    from sie.domain.engines.technical_seo import run_technical_audit
    from sie.infrastructure.parsing.html_parser import Bs4PageParser

    parser = Bs4PageParser()
    parsed = {page.url: parser.parse_page(page) for page in pages}
    extractions = {page.url: parser.parse_links(page) for page in pages}
    technical = run_technical_audit(list(parsed.values()), link_extractions=extractions)

    # Compute architecture for evidence
    from sie.domain.engines.link_graph import build_architecture_report

    architecture = build_architecture_report(pages, extractions)

    # Compute content metrics for evidence
    from sie.domain.engines.content_intelligence import analyze_content_batch

    html_map: dict[str, str] = {}
    for page in pages:
        if page.is_html:
            html_map[page.url] = page.decoded_text()
        else:
            html_map[page.url] = ""
    content_metrics = analyze_content_batch(list(parsed.values()), html_map)

    # Compute content comparisons
    from sie.domain.engines.content_comparison import find_duplicate_groups

    comparisons = []
    groups = find_duplicate_groups(content_metrics)
    for group in groups:
        if len(group) >= 2:
            from sie.domain.engines.content_comparison import compare_content

            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    m_a = next((m for m in content_metrics if m.url == group[i]), None)
                    m_b = next((m for m in content_metrics if m.url == group[j]), None)
                    if m_a and m_b:
                        comparisons.append(compare_content(m_a, m_b))

    evidence = build_evidence_package(
        run_id=body.run_id,
        technical=technical,
        architecture=architecture,
        content_metrics=content_metrics,
        content_comparisons=comparisons,
        diagnosis=diagnosis,
        crawled_page_count=len(pages),
        status_distribution=status_dist,
    )

    # Generate report
    report = await svc.generate_report(body.run_id, diagnosis, evidence)

    # Persist report
    repo = _repository(request)
    await repo.save_intelligence_report(body.run_id, report)

    return IntelligenceResponse(
        intelligence_id=report.intelligence_id,
        status="completed",
        summary=report.summary,
        top_issue_count=len(report.top_issues),
        action_count=len(report.action_plan),
    )


@router.get("/{intelligence_id}", response_model=IntelligenceDetailResponse)
async def get_intelligence_report(intelligence_id: str, request: Request):
    """Retrieve a persisted intelligence report by ID."""
    repo = _repository(request)
    report = await repo.get_intelligence_report(intelligence_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="intelligence report not found"
        )
    return _detail_response(report)


@router.get("/{intelligence_id}/actions", response_model=ActionPlanResponse)
async def get_action_plan(intelligence_id: str, request: Request):
    """Retrieve only the prioritized action plan from an intelligence report."""
    repo = _repository(request)
    report = await repo.get_intelligence_report(intelligence_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="intelligence report not found"
        )
    return ActionPlanResponse(
        intelligence_id=report.intelligence_id,
        total_actions=len(report.action_plan),
        actions=[
            ActionPlanItemResponse(
                order=ap.order,
                action=ap.action,
                reason=ap.reason,
                priority=ap.priority,
                difficulty=ap.difficulty,
                dependencies=list(ap.dependencies),
            )
            for ap in report.action_plan
        ],
    )


def _detail_response(report) -> IntelligenceDetailResponse:
    return IntelligenceDetailResponse(
        intelligence_id=report.intelligence_id,
        run_id=report.run_id,
        status="completed",
        prompt_version=report.prompt_version,
        model_name=report.model_name,
        provider=report.provider,
        summary=report.summary,
        overall_assessment=report.overall_assessment,
        root_causes=[
            RootCauseResponse(
                title=rc.title,
                evidence=list(rc.evidence),
                confidence=rc.confidence,
            )
            for rc in report.root_causes
        ],
        top_issues=[
            TopIssueResponse(
                issue_code=ti.issue_code,
                title=ti.title,
                interpretation=ti.interpretation,
                impact=ti.impact,
                confidence=ti.confidence,
                affected_url_count=ti.affected_url_count,
            )
            for ti in report.top_issues
        ],
        quick_wins=[
            QuickWinResponse(
                action=qw.action,
                reason=qw.reason,
                priority=qw.priority,
                difficulty=qw.difficulty,
            )
            for qw in report.quick_wins
        ],
        action_plan=[
            ActionPlanItemResponse(
                order=ap.order,
                action=ap.action,
                reason=ap.reason,
                priority=ap.priority,
                difficulty=ap.difficulty,
                dependencies=list(ap.dependencies),
            )
            for ap in report.action_plan
        ],
    )
