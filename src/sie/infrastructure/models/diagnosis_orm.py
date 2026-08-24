"""SQLAlchemy ORM models for SEO diagnosis persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sie.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    from sie.infrastructure.models.crawl_orm import CrawlRunRow


class DiagnosisResultRow(Base):
    __tablename__ = "diagnosis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    total_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issues_by_priority: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    issues_by_severity: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    issues_by_category: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    top_affected_pages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    run: Mapped[CrawlRunRow] = relationship(back_populates="diagnosis_result")
