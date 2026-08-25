"""SQLAlchemy ORM models for content intelligence persistence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sie.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    from sie.infrastructure.models.crawl_orm import CrawlRunRow


class ContentTypeEnum(StrEnum):
    ARTICLE = "article"
    PRODUCT = "product"
    CATEGORY = "category"
    LANDING = "landing"
    BLOG_POST = "blog_post"
    NEWS = "news"
    DOCUMENTATION = "documentation"
    FORUM = "forum"
    CONTACT = "contact"
    ABOUT = "about"
    HOME = "home"
    SEARCH = "search"
    TAG = "tag"
    AUTHOR = "author"
    ERROR = "error"
    OTHER = "other"


class QualityTierEnum(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    THIN = "thin"


class DuplicateStatusEnum(StrEnum):
    UNIQUE = "unique"
    NEAR_DUPLICATE = "near_duplicate"
    EXACT_DUPLICATE = "exact_duplicate"


class ContentMetricsRow(Base):
    __tablename__ = "content_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("crawl_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)

    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    visible_text: Mapped[str] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    type_token_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paragraph_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_words_per_sentence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_sentences_per_paragraph: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stopword_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    html_to_text_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    readability: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    headings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    images: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    links: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    structured_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    freshness: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    multimedia: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    keywords: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_tier: Mapped[str] = mapped_column(String(16), nullable=False, default="thin")
    thin_content: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)

    extracted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    run: Mapped[CrawlRunRow] = relationship(back_populates="content_metrics")


class ContentComparisonRow(Base):
    __tablename__ = "content_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("crawl_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url_a: Mapped[str] = mapped_column(Text, nullable=False)
    url_b: Mapped[str] = mapped_column(Text, nullable=False)

    similarity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    jaccard_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cosine_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    word_overlap_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_overlap_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    structural_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duplicate_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unique")

    compared_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    run: Mapped[CrawlRunRow] = relationship(back_populates="content_comparisons")


class ContentQualityReportRow(Base):
    __tablename__ = "content_quality_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analyzed_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_distribution: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    thin_content_pages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    duplicate_groups: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    top_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    run: Mapped[CrawlRunRow] = relationship(back_populates="content_quality_report")


# Need to add relationships to CrawlRunRow - but that's in crawl_orm.py
# We'll add them there
