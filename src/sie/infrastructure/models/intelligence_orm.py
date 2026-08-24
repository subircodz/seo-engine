"""SQLAlchemy ORM models for intelligence report persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sie.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    from sie.infrastructure.models.crawl_orm import CrawlRunRow


class IntelligenceReportRow(Base):
    __tablename__ = "intelligence_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intelligence_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, unique=True
    )
    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    diagnosis_run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)

    summary: Mapped[str] = mapped_column(String, nullable=False)
    overall_assessment: Mapped[str] = mapped_column(String, nullable=False)
    root_causes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    top_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    quick_wins: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    action_plan: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_response: Mapped[str] = mapped_column(String, nullable=False, default="")

    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    run: Mapped[CrawlRunRow] = relationship(back_populates="intelligence_reports")
