"""SQLAlchemy ORM models for search dataset persistence (Phase 6E)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sie.infrastructure.persistence.database import Base


class SearchDatasetRow(Base):
    __tablename__ = "search_datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_keywords: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_observations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    keywords: Mapped[list[SearchKeywordRow]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="SearchKeywordRow.id",
    )
    observations: Mapped[list[SearchRankingObservationRow]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="SearchRankingObservationRow.id",
    )
    competitor_rankings: Mapped[list[SearchCompetitorRankingRow]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="SearchCompetitorRankingRow.id",
    )


class SearchKeywordRow(Base):
    __tablename__ = "search_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("search_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    search_intent: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")

    dataset: Mapped[SearchDatasetRow] = relationship(back_populates="keywords")


class SearchRankingObservationRow(Base):
    __tablename__ = "search_ranking_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("search_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    search_engine: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    country: Mapped[str] = mapped_column(String(8), nullable=False, default="us")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    device: Mapped[str] = mapped_column(String(16), nullable=False, default="desktop")
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    serp_features: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)

    dataset: Mapped[SearchDatasetRow] = relationship(back_populates="observations")


class SearchCompetitorRankingRow(Base):
    __tablename__ = "search_competitor_rankings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("search_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    competitor_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    competitor_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    dataset: Mapped[SearchDatasetRow] = relationship(back_populates="competitor_rankings")


# Composite lookup index mirroring the Phase 6C duplicate-identity check:
# normalized keyword + URL + device + timestamp.
Index(
    "ix_search_obs_identity",
    SearchRankingObservationRow.keyword,
    SearchRankingObservationRow.target_url,
    SearchRankingObservationRow.device,
    SearchRankingObservationRow.observed_at,
)
