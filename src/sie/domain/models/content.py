"""Content intelligence domain models.

Pure dataclasses for deterministic content analysis — zero I/O, zero framework deps.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ContentType(StrEnum):
    """Deterministic content-type classification."""

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


class QualityTier(StrEnum):
    """Content quality tier based on composite score."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    THIN = "thin"


class DuplicateStatus(StrEnum):
    """Duplicate detection result."""

    UNIQUE = "unique"
    NEAR_DUPLICATE = "near_duplicate"
    EXACT_DUPLICATE = "exact_duplicate"


@dataclass(frozen=True, slots=True)
class ReadabilityMetrics:
    """Readability scores (all deterministic formulas)."""

    flesch_reading_ease: float
    flesch_kincaid_grade: float
    gunning_fog_index: float
    smog_index: float
    automated_readability_index: float
    coleman_liau_index: float
    lix: float
    rix: float
    word_count: int
    sentence_count: int
    syllable_count: int


@dataclass(frozen=True, slots=True)
class HeadingAnalysis:
    """Heading structure analysis."""

    h1_count: int
    h2_count: int
    h3_count: int
    h4_count: int
    h5_count: int
    h6_count: int
    h1_texts: tuple[str, ...]
    h2_texts: tuple[str, ...]
    h3_texts: tuple[str, ...]
    has_h1: bool
    h1_matches_title: bool
    heading_depth: int
    heading_keyword_coverage: float


@dataclass(frozen=True, slots=True)
class ImageAnalysis:
    """Image and alt-text analysis."""

    total_images: int
    images_with_alt: int
    images_without_alt: int
    images_with_empty_alt: int
    decorative_images: int
    alt_texts: tuple[str, ...]
    missing_alt_percentage: float
    avg_alt_length: float
    has_lazy_loading: bool
    has_webp: bool


@dataclass(frozen=True, slots=True)
class LinkAnalysis:
    """Internal/external link analysis."""

    internal_links: int
    external_links: int
    nofollow_links: int
    internal_link_ratio: float
    external_domains: int
    anchor_texts: tuple[str, ...]
    empty_anchors: int
    generic_anchors: int
    keyword_rich_anchors: int
    anchor_diversity: float


@dataclass(frozen=True, slots=True)
class StructuredDataAnalysis:
    """Structured data extraction."""

    jsonld_types: tuple[str, ...]
    microdata_types: tuple[str, ...]
    rdfa_types: tuple[str, ...]
    has_schema_org: bool
    schema_count: int
    validation_errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FreshnessAnalysis:
    """Content freshness signals."""

    published_date: datetime | None
    modified_date: datetime | None
    has_date_signals: bool
    days_since_published: int | None
    days_since_modified: int | None
    is_stale: bool
    freshness_score: float


@dataclass(frozen=True, slots=True)
class MultimediaAnalysis:
    """Multimedia content detection."""

    has_video: bool
    has_audio: bool
    has_iframe_embeds: int
    has_pdf_links: int
    has_image_galleries: bool
    video_count: int
    audio_count: int
    embed_domains: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KeywordDensity:
    """Keyword density analysis."""

    top_keywords: tuple[tuple[str, int, float], ...]
    bigram_density: tuple[tuple[str, int, float], ...]
    trigram_density: tuple[tuple[str, int, float], ...]
    keyword_stuffing_score: float


@dataclass(frozen=True, slots=True)
class ContentMetrics:
    """Core content metrics."""

    url: str
    content_type: ContentType
    visible_text: str
    word_count: int
    unique_word_count: int
    type_token_ratio: float
    character_count: int
    paragraph_count: int
    avg_words_per_sentence: float
    avg_sentences_per_paragraph: float
    stopword_ratio: float
    html_to_text_ratio: float
    readability: ReadabilityMetrics
    headings: HeadingAnalysis
    images: ImageAnalysis
    links: LinkAnalysis
    structured_data: StructuredDataAnalysis
    freshness: FreshnessAnalysis
    multimedia: MultimediaAnalysis
    keywords: KeywordDensity
    quality_score: float
    quality_tier: QualityTier
    thin_content: bool
    extracted_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class ContentComparison:
    """Pairwise content comparison result."""

    url_a: str
    url_b: str
    similarity_score: float
    jaccard_similarity: float
    cosine_similarity: float
    word_overlap_count: int
    word_overlap_ratio: float
    structural_similarity: float
    duplicate_status: DuplicateStatus
    compared_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class ContentQualityReport:
    """Aggregated content quality report for a crawl run."""

    run_id: str
    total_pages: int
    analyzed_pages: int
    avg_quality_score: float
    quality_distribution: Mapping[QualityTier, int]
    thin_content_pages: tuple[str, ...]
    duplicate_groups: tuple[tuple[str, ...], ...]
    top_issues: tuple[tuple[str, int], ...]
    generated_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class ContentAnalysisConfig:
    """Configuration for content analysis engine."""

    min_word_count: int = 300
    thin_content_threshold: int = 150
    duplicate_similarity_threshold: float = 0.85
    near_duplicate_threshold: float = 0.70
    keyword_stuffing_threshold: float = 0.05
    max_keywords: int = 50
    enable_readability: bool = True
    enable_keywords: bool = True
    enable_comparison: bool = True
    stopwords_language: str = "en"
