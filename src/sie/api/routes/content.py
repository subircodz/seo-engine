"""Content Intelligence API endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

from sie.api.auth import api_key_auth
from sie.domain.models.content import (
    ContentAnalysisConfig,
    ContentComparison,
    ContentMetrics,
    ContentQualityReport,
    ContentType,
    QualityTier,
)

router = APIRouter(
    prefix="/api/content",
    tags=["content"],
    dependencies=[Depends(api_key_auth)],
)


# ── request / response models ─────────────────────────────────────────────────


class ContentAnalysisRequest(BaseModel):
    run_id: str
    config: ContentAnalysisConfig | None = None


class ContentMetricsResponse(BaseModel):
    url: str
    content_type: str
    word_count: int
    unique_word_count: int
    type_token_ratio: float
    character_count: int
    paragraph_count: int
    avg_words_per_sentence: float
    avg_sentences_per_paragraph: float
    stopword_ratio: float
    html_to_text_ratio: float
    quality_score: float
    quality_tier: str
    thin_content: bool
    extracted_at: str


class ContentAnalysisResponse(BaseModel):
    run_id: str
    status: str
    total_pages: int
    analyzed_pages: int
    avg_quality_score: float
    items: list[ContentMetricsResponse]


class ContentComparisonResponse(BaseModel):
    url_a: str
    url_b: str
    similarity_score: float
    jaccard_similarity: float
    cosine_similarity: float
    word_overlap_count: int
    word_overlap_ratio: float
    structural_similarity: float
    duplicate_status: str
    compared_at: str


class ContentComparisonListResponse(BaseModel):
    run_id: str
    total: int
    items: list[ContentComparisonResponse]


class ContentQualityReportResponse(BaseModel):
    run_id: str
    total_pages: int
    analyzed_pages: int
    avg_quality_score: float
    quality_distribution: dict[str, int]
    thin_content_pages: list[str]
    duplicate_groups: list[list[str]]
    top_issues: list[list[str | int]]
    generated_at: str


class PageMetricsResponse(BaseModel):
    url: str
    content_type: str
    word_count: int
    unique_word_count: int
    type_token_ratio: float
    character_count: int
    paragraph_count: int
    avg_words_per_sentence: float
    avg_sentences_per_paragraph: float
    stopword_ratio: float
    html_to_text_ratio: float
    readability: dict
    headings: dict
    images: dict
    links: dict
    structured_data: dict
    freshness: dict
    multimedia: dict
    keywords: dict
    quality_score: float
    quality_tier: str
    thin_content: bool
    extracted_at: str


# ── helpers ───────────────────────────────────────────────────────────────────


def _content_service(request: Request):
    return request.app.state.content_service


def _crawled_pages(request: Request):
    return request.app.state.crawled_pages


def _metrics_to_response(m: ContentMetrics) -> ContentMetricsResponse:
    return ContentMetricsResponse(
        url=m.url,
        content_type=m.content_type.value,
        word_count=m.word_count,
        unique_word_count=m.unique_word_count,
        type_token_ratio=m.type_token_ratio,
        character_count=m.character_count,
        paragraph_count=m.paragraph_count,
        avg_words_per_sentence=m.avg_words_per_sentence,
        avg_sentences_per_paragraph=m.avg_sentences_per_paragraph,
        stopword_ratio=m.stopword_ratio,
        html_to_text_ratio=m.html_to_text_ratio,
        quality_score=m.quality_score,
        quality_tier=m.quality_tier.value,
        thin_content=m.thin_content,
        extracted_at=m.extracted_at.isoformat(),
    )


def _full_metrics_to_response(m: ContentMetrics) -> PageMetricsResponse:
    return PageMetricsResponse(
        url=m.url,
        content_type=m.content_type.value,
        word_count=m.word_count,
        unique_word_count=m.unique_word_count,
        type_token_ratio=m.type_token_ratio,
        character_count=m.character_count,
        paragraph_count=m.paragraph_count,
        avg_words_per_sentence=m.avg_words_per_sentence,
        avg_sentences_per_paragraph=m.avg_sentences_per_paragraph,
        stopword_ratio=m.stopword_ratio,
        html_to_text_ratio=m.html_to_text_ratio,
        readability=asdict(m.readability),
        headings=asdict(m.headings),
        images=asdict(m.images),
        links=asdict(m.links),
        structured_data=asdict(m.structured_data),
        freshness=asdict(m.freshness),
        multimedia=asdict(m.multimedia),
        keywords=asdict(m.keywords),
        quality_score=m.quality_score,
        quality_tier=m.quality_tier.value,
        thin_content=m.thin_content,
        extracted_at=m.extracted_at.isoformat(),
    )


def _comparison_to_response(c: ContentComparison) -> ContentComparisonResponse:
    return ContentComparisonResponse(
        url_a=c.url_a,
        url_b=c.url_b,
        similarity_score=c.similarity_score,
        jaccard_similarity=c.jaccard_similarity,
        cosine_similarity=c.cosine_similarity,
        word_overlap_count=c.word_overlap_count,
        word_overlap_ratio=c.word_overlap_ratio,
        structural_similarity=c.structural_similarity,
        duplicate_status=c.duplicate_status.value,
        compared_at=c.compared_at.isoformat(),
    )


def _quality_report_to_response(r: ContentQualityReport) -> ContentQualityReportResponse:
    return ContentQualityReportResponse(
        run_id=r.run_id,
        total_pages=r.total_pages,
        analyzed_pages=r.analyzed_pages,
        avg_quality_score=r.avg_quality_score,
        quality_distribution={k.value: v for k, v in r.quality_distribution.items()},
        thin_content_pages=list(r.thin_content_pages),
        duplicate_groups=[list(g) for g in r.duplicate_groups],
        top_issues=[list(i) for i in r.top_issues],
        generated_at=r.generated_at.isoformat(),
    )


# ── Content Analysis ─────────────────────────────────────────────────────────


@router.post("/analyze", status_code=status.HTTP_200_OK, response_model=ContentAnalysisResponse)
async def analyze_content(body: ContentAnalysisRequest, request: Request):
    svc = _content_service(request)
    pages = _crawled_pages(request).get(body.run_id)
    if pages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl run not found")

    config = body.config or ContentAnalysisConfig()
    metrics = await svc.analyze_content(body.run_id, pages, config)

    total = len(metrics)
    avg_score = sum(m.quality_score for m in metrics) / total if total > 0 else 0.0

    return ContentAnalysisResponse(
        run_id=body.run_id,
        status="completed",
        total_pages=total,
        analyzed_pages=total,
        avg_quality_score=round(avg_score, 2),
        items=[_metrics_to_response(m) for m in metrics],
    )


@router.get("/analyze/{run_id}", response_model=ContentAnalysisResponse)
async def get_content_analysis(run_id: str, request: Request):
    svc = _content_service(request)
    metrics = svc.get_analysis(run_id)
    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="content analysis not found",
        )

    total = len(metrics)
    avg_score = sum(m.quality_score for m in metrics) / total if total > 0 else 0.0

    return ContentAnalysisResponse(
        run_id=run_id,
        status="completed",
        total_pages=total,
        analyzed_pages=total,
        avg_quality_score=round(avg_score, 2),
        items=[_metrics_to_response(m) for m in metrics],
    )


@router.get("/analyze/{run_id}/pages", response_model=list[ContentMetricsResponse])
async def list_content_pages(
    run_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    svc = _content_service(request)
    metrics = svc.get_analysis(run_id)
    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="content analysis not found",
        )

    page = metrics[offset : offset + limit]
    return [_metrics_to_response(m) for m in page]


@router.get("/analyze/{run_id}/pages/{url:path}", response_model=PageMetricsResponse)
async def get_page_metrics(run_id: str, url: str, request: Request):
    svc = _content_service(request)
    metrics = await svc.get_page_metrics(run_id, url)
    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="page metrics not found",
        )
    return _full_metrics_to_response(metrics)


@router.get(
    "/analyze/{run_id}/by-type/{content_type}",
    response_model=list[ContentMetricsResponse],
)
async def get_pages_by_type(run_id: str, content_type: str, request: Request):
    svc = _content_service(request)
    try:
        ContentType(content_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid content type: {content_type}",
        ) from exc
    metrics = await svc.get_pages_by_type(run_id, content_type)
    return [_metrics_to_response(m) for m in metrics]


@router.get(
    "/analyze/{run_id}/by-quality/{quality_tier}",
    response_model=list[ContentMetricsResponse],
)
async def get_pages_by_quality(run_id: str, quality_tier: str, request: Request):
    svc = _content_service(request)
    try:
        QualityTier(quality_tier)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid quality tier: {quality_tier}",
        ) from exc
    metrics = await svc.get_pages_by_quality(run_id, QualityTier(quality_tier))
    return [_metrics_to_response(m) for m in metrics]


# ── Content Comparison ────────────────────────────────────────────────────────


@router.post(
    "/compare",
    status_code=status.HTTP_200_OK,
    response_model=ContentComparisonListResponse,
)
async def run_content_comparison(body: ContentAnalysisRequest, request: Request):
    svc = _content_service(request)
    pages = _crawled_pages(request).get(body.run_id)
    if pages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="crawl run not found",
        )

    config = body.config or ContentAnalysisConfig()
    metrics = await svc.analyze_content(body.run_id, pages, config)
    comparisons = await svc.run_comparison(body.run_id, metrics, config)

    return ContentComparisonListResponse(
        run_id=body.run_id,
        total=len(comparisons),
        items=[_comparison_to_response(c) for c in comparisons],
    )


@router.get("/compare/{run_id}", response_model=ContentComparisonListResponse)
async def get_content_comparisons(run_id: str, request: Request):
    svc = _content_service(request)
    comparisons = svc.get_comparisons(run_id)
    if comparisons is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="content comparison not found",
        )

    return ContentComparisonListResponse(
        run_id=run_id,
        total=len(comparisons),
        items=[_comparison_to_response(c) for c in comparisons],
    )


@router.get("/compare/{run_id}/duplicates", response_model=list[ContentComparisonResponse])
async def get_duplicate_pages(run_id: str, request: Request):
    svc = _content_service(request)
    comparisons = svc.get_comparisons(run_id)
    if comparisons is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="content comparison not found",
        )

    dups = [c for c in comparisons if c.duplicate_status != "unique"]
    return [_comparison_to_response(c) for c in dups]


# ── Content Quality Report ────────────────────────────────────────────────────


@router.post(
    "/quality-report",
    status_code=status.HTTP_200_OK,
    response_model=ContentQualityReportResponse,
)
async def generate_quality_report(body: ContentAnalysisRequest, request: Request):
    svc = _content_service(request)
    pages = _crawled_pages(request).get(body.run_id)
    if pages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="crawl run not found",
        )

    config = body.config or ContentAnalysisConfig()
    metrics = await svc.analyze_content(body.run_id, pages, config)
    report = await svc.generate_quality_report(body.run_id, metrics)

    return _quality_report_to_response(report)


@router.get("/quality-report/{run_id}", response_model=ContentQualityReportResponse)
async def get_quality_report(run_id: str, request: Request):
    svc = _content_service(request)
    report = svc.get_quality_report(run_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="quality report not found",
        )
    return _quality_report_to_response(report)
