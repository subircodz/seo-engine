"""SQLAlchemy ORM models for crawl persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sie.infrastructure.models.content_orm import (
    ContentComparisonRow,
    ContentMetricsRow,
    ContentQualityReportRow,
)
from sie.infrastructure.models.diagnosis_orm import DiagnosisResultRow
from sie.infrastructure.models.intelligence_orm import IntelligenceReportRow
from sie.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    from sie.infrastructure.models.crawl_orm import CrawlRunRow


class CrawlRunRow(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    pages: Mapped[list["CrawlPageRow"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="CrawlPageRow.id",
    )

    # Phase 4: Content Intelligence relationships
    content_metrics: Mapped[list["ContentMetricsRow"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    content_comparisons: Mapped[list["ContentComparisonRow"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    content_quality_report: Mapped["ContentQualityReportRow | None"] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # Phase 5: Diagnosis relationship
    diagnosis_result: Mapped["DiagnosisResultRow | None"] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )

# Phase 5C: Intelligence report relationship
    intelligence_reports: Mapped[list["IntelligenceReportRow"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # Site analysis results
    site_analysis_results: Mapped[list["SiteAnalysisResultRow"]] = relationship(
        back_populates="crawl_run",
        cascade="all, delete-orphan",
    )


class CrawlPageRow(Base):
    __tablename__ = "crawl_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    html_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["CrawlRunRow"] = relationship(back_populates="pages")


class SiteAnalysisResultRow(Base):
    """Persisted site analysis result for historical comparison."""

    __tablename__ = "site_analysis_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    crawl_run_id: Mapped[str] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Core health scores (0-100)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    technical_score: Mapped[float] = mapped_column(Float, nullable=False)
    content_score: Mapped[float] = mapped_column(Float, nullable=False)
    ranking_score: Mapped[float] = mapped_column(Float, nullable=False)
    architecture_score: Mapped[float] = mapped_column(Float, nullable=False)
    aio_score: Mapped[float] = mapped_column(Float, nullable=False)
    geo_score: Mapped[float] = mapped_column(Float, nullable=False)
    javascript_score: Mapped[float] = mapped_column(Float, nullable=False)
    structured_data_score: Mapped[float] = mapped_column(Float, nullable=False)
    core_web_vitals_score: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_coverage_score: Mapped[float] = mapped_column(Float, nullable=False)
    internal_link_equity_score: Mapped[float] = mapped_column(Float, nullable=False)
    search_intent_score: Mapped[float] = mapped_column(Float, nullable=False)
    serp_features_score: Mapped[float] = mapped_column(Float, nullable=False)
    competitor_gaps_score: Mapped[float] = mapped_column(Float, nullable=False)
    indexation_score: Mapped[float] = mapped_column(Float, nullable=False)
    eeat_score: Mapped[float] = mapped_column(Float, nullable=False)
    content_decay_score: Mapped[float] = mapped_column(Float, nullable=False)
    entity_kg_score: Mapped[float] = mapped_column(Float, nullable=False)
    advanced_competitor_score: Mapped[float] = mapped_column(Float, nullable=False)
    hreflang_score: Mapped[float] = mapped_column(Float, nullable=False)
    advanced_link_score: Mapped[float] = mapped_column(Float, nullable=False)
    predictive_ranking_score: Mapped[float] = mapped_column(Float, nullable=False)
    rag_optimization_score: Mapped[float] = mapped_column(Float, nullable=False)
    content_quality_adv_score: Mapped[float] = mapped_column(Float, nullable=False)
    pagination_faceted_score: Mapped[float] = mapped_column(Float, nullable=False)
    amp_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Overall grade
    overall_grade: Mapped[str] = mapped_column(String(2), nullable=False)  # A+, A, B+, B, C+, C, D, F

    # Full analysis JSON for drill-down
    analysis_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # CrUX data (if available)
    crux_lcp: Mapped[float | None] = mapped_column(Float, nullable=True)
    crux_fid: Mapped[float | None] = mapped_column(Float, nullable=True)
    crux_cls: Mapped[float | None] = mapped_column(Float, nullable=True)
    crux_inp: Mapped[float | None] = mapped_column(Float, nullable=True)
    crux_ttfb: Mapped[float | None] = mapped_column(Float, nullable=True)
    crux_last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    crawl_run: Mapped["CrawlRunRow"] = relationship(back_populates="site_analysis_results")
