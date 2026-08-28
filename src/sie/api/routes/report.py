"""Report download endpoints — PDF export for intelligence reports.

Phase 12D: PDF export layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from sie.api.auth import api_key_auth

__all__ = ["router"]

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(api_key_auth)],
)


class ReportDataRequest(BaseModel):
    """Request to generate PDF from analysis data directly."""

    intelligence_id: str
    summary: str = ""
    findings: list[dict] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)


@router.get("/{report_id}/pdf", response_class=Response)
async def download_report_pdf(report_id: str, request: Request) -> Response:
    """Download an intelligence report as PDF.

    Args:
        report_id: The report identifier.

    Returns:
        PDF file response.
    """
    from sie.domain.renderers.pdf_renderer import PDFGenerationError, PDFRenderer

    renderer = PDFRenderer()

    async with request.app.state.database.session_factory() as session:
        from sqlalchemy import select

        from sie.infrastructure.models.industry_orm import IndustryIntelligenceRow
        from sie.infrastructure.models.intelligence_orm import IntelligenceReportRow

        report_row = (
            await session.execute(
                select(IntelligenceReportRow).where(
                    IntelligenceReportRow.intelligence_id == report_id
                )
            )
        ).scalar_one_or_none()

        if report_row:
            report_data = {
                "intelligence_id": report_row.intelligence_id,
                "summary": report_row.summary,
                "generated_at": report_row.generated_at,
            }
        else:
            industry_row = (
                await session.execute(
                    select(IndustryIntelligenceRow).where(
                        IndustryIntelligenceRow.dataset_id == report_id
                    )
                )
            ).scalar_one_or_none()

            if industry_row:
                import json

                findings = json.loads(industry_row.findings) if industry_row.findings else []
                opportunities = (
                    json.loads(industry_row.opportunities) if industry_row.opportunities else []
                )

                summary_text = (
                    f"Industry Intelligence Report - "
                    f"{len(findings)} findings, {len(opportunities)} opportunities"
                )
                report_data = {
                    "intelligence_id": report_id,
                    "summary": summary_text,
                    "generated_at": industry_row.generated_at,
                    "findings": findings,
                    "recommendations": opportunities,
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Report {report_id} not found",
                )

    try:
        pdf_bytes = renderer.render(report_data)
    except PDFGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{report_id}.pdf"'},
    )


@router.post("/generate-pdf", response_class=Response)
async def generate_pdf_from_analysis(body: ReportDataRequest) -> Response:
    """Generate PDF directly from analysis data (no database persistence required)."""
    from sie.domain.renderers.pdf_renderer import PDFGenerationError, PDFRenderer

    renderer = PDFRenderer()

    from datetime import UTC, datetime

    report_data = {
        "intelligence_id": body.intelligence_id,
        "summary": body.summary
        or (
            f"Search Intelligence Report - {len(body.findings)} findings, "
            f"{len(body.recommendations)} recommendations"
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "findings": body.findings,
        "recommendations": body.recommendations,
    }

    try:
        pdf_bytes = renderer.render(report_data)
    except PDFGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report_{body.intelligence_id}.pdf"'
        },
    )
