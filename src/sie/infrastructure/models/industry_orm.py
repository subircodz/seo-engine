"""SQLAlchemy ORM models for industry intelligence persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sie.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    from sie.infrastructure.models.search_orm import SearchDatasetRow


class IndustryIntelligenceRow(Base):
    __tablename__ = "industry_intelligence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("search_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    profile: Mapped[str] = mapped_column(String(64), nullable=False)
    total_keywords: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visibility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    aio_visibility: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    geo_visibility: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cannibalization_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    volatility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    findings: Mapped[list] = mapped_column(Text, nullable=False, default="")
    opportunities: Mapped[list] = mapped_column(Text, nullable=False, default="")

    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    dataset: Mapped[SearchDatasetRow] = relationship(back_populates="industry_intelligence")
