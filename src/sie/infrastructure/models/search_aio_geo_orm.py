"""SQLAlchemy ORM models for AIO/GEO observations and evidence provenance."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sie.infrastructure.persistence.database import Base


class AIOverviewObservationRow(Base):
    __tablename__ = "aio_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("search_datasets.id", ondelete="CASCADE"), nullable=False
    )
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    ai_type: Mapped[str] = mapped_column(String(32), nullable=False)
    present: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    target_cited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_domain: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    citations: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    competitor_cited_domains: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="manual")
    observation_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    methodology: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class GEOObservationRow(Base):
    __tablename__ = "geo_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("search_datasets.id", ondelete="CASCADE"), nullable=False
    )
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    engine_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_mentioned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_domain: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entity_mentions: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    competitor_domains: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    citation_urls: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    answer_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="manual")
    observation_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    methodology: Mapped[str | None] = mapped_column(String(1024), nullable=True)


Index(
    "ix_aio_obs_dataset_keyword",
    AIOverviewObservationRow.dataset_id,
    AIOverviewObservationRow.keyword,
)
Index("ix_geo_obs_dataset_keyword", GEOObservationRow.dataset_id, GEOObservationRow.keyword)
