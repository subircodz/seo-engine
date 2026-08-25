"""SQLAlchemy ORM models for Performance, Entity, and Optimization persistence (Phase 8)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sie.infrastructure.persistence.database import Base


class PerformanceFindingRow(Base):
    """ORM model for persisting performance analysis findings."""

    __tablename__ = "performance_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("search_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    recommendation: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EntitySignalRow(Base):
    """ORM model for persisting entity signals."""

    __tablename__ = "entity_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("search_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    entity_text: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_target: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OptimizationRecommendationRow(Base):
    """ORM model for persisting optimization recommendations."""

    __tablename__ = "optimization_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("search_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(String(4096), nullable=False)
    impact: Mapped[str] = mapped_column(String(16), nullable=False)
    effort: Mapped[str] = mapped_column(String(16), nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    affected_keywords: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    affected_urls: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source_engine: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# Composite indexes
Index(
    "ix_perf_findings_dataset_url",
    PerformanceFindingRow.dataset_id,
    PerformanceFindingRow.url,
)
Index(
    "ix_entity_signals_dataset_keyword",
    EntitySignalRow.dataset_id,
    EntitySignalRow.keyword,
)
Index(
    "ix_opt_recs_dataset_category",
    OptimizationRecommendationRow.dataset_id,
    OptimizationRecommendationRow.category,
)
