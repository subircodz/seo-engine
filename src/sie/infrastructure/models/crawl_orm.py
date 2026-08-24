"""SQLAlchemy ORM models for crawl persistence."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sie.infrastructure.models.content_orm import (
    ContentComparisonRow,
    ContentMetricsRow,
    ContentQualityReportRow,
)
from sie.infrastructure.models.diagnosis_orm import DiagnosisResultRow
from sie.infrastructure.models.intelligence_orm import IntelligenceReportRow
from sie.infrastructure.persistence.database import Base


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
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["CrawlRunRow"] = relationship(back_populates="pages")
