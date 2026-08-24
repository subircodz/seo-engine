"""Generative Engine Optimization (GEO) intelligence domain models (Phase 6N-G).

Immutable value objects representing observations of generative engine
visibility — how a brand/domain/entity appears in LLM-generated answers,
AI-powered search, and generative search experiences.

These models are provider-neutral and capture only the essential,
vendor-neutral aspects of generative visibility.  They do NOT couple
to any specific LLM provider or search engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utc_now() -> datetime:
    return datetime.now(UTC)


class GenerativeEngineType(StrEnum):
    """Types of generative engines / AI-powered search systems."""

    GOOGLE_AI_OVERVIEW = "google_ai_overview"
    BING_COPILOT = "bing_copilot"
    PERPLEXITY = "perplexity"
    CHATGPT = "chatgpt"
    CLAUDE = "claude"
    GEMINI = "gemini"
    OTHER = "other"


class EntityType(StrEnum):
    """Type of entity mentioned in a generative answer."""

    BRAND = "brand"
    """Company/brand name."""

    PRODUCT = "product"
    """Specific product name."""

    PERSON = "person"
    """Person/author name."""

    LOCATION = "location"
    """Geographic location."""

    ORGANIZATION = "organization"
    """Organization (broader than brand)."""

    OTHER = "other"
    """Other entity type."""


@dataclass(frozen=True, slots=True)
class EntityMention:
    """An entity/brand mentioned within a generative answer.

    Captures the entity text, type, and whether it refers to the tracked
    domain/brand.
    """

    text: str
    """The entity text as it appears in the answer."""

    entity_type: EntityType = EntityType.BRAND
    """Type of entity."""

    is_target: bool = False
    """Whether this entity refers to the tracked target brand/domain."""

    domain: str = ""
    """Associated domain, if the entity maps to a web entity."""

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("text must be a non-empty string")


@dataclass(frozen=True, slots=True)
class GEOObservation:
    """A single observation of generative engine visibility for a keyword.

    Records whether the target brand/domain/entity was mentioned in a
    generative answer, and which competitors appeared.
    """

    keyword: str
    """The search query / keyword observed."""

    engine_type: GenerativeEngineType
    """Which generative engine was observed."""

    target_mentioned: bool = False
    """Whether the target brand/domain was mentioned in the answer."""

    target_domain: str = ""
    """The target domain/brand being tracked."""

    mention_count: int = 0
    """Number of times the target was mentioned."""

    entity_mentions: tuple[EntityMention, ...] = ()
    """All entity mentions in the generative answer."""

    competitor_domains: tuple[str, ...] = ()
    """Competitor domains mentioned in the answer."""

    citation_urls: tuple[str, ...] = ()
    """URLs cited as sources in the generative answer."""

    answer_length: int = 0
    """Approximate length of the generated answer (characters)."""

    observed_at: datetime = field(default_factory=_utc_now)
    """When this observation was recorded."""

    source: str = "manual"
    """Provider/system that produced this observation."""

    def __post_init__(self) -> None:
        if not self.keyword or not self.keyword.strip():
            raise ValueError("keyword must be a non-empty string")
        normalised = " ".join(self.keyword.split()).casefold()
        if normalised != self.keyword:
            object.__setattr__(self, "keyword", normalised)
        if self.target_domain:
            norm_domain = self.target_domain.casefold().removeprefix("www.").strip()
            if norm_domain != self.target_domain:
                object.__setattr__(self, "target_domain", norm_domain)


@dataclass(frozen=True, slots=True)
class GEOMetrics:
    """Aggregated GEO metrics for a single keyword across observations."""

    keyword: str
    observation_count: int
    target_mentioned_count: int
    competitor_mentioned_count: int
    mention_rate: float
    """Fraction of observations where target was mentioned (0.0-1.0)."""
    avg_mention_count: float
    """Average number of target mentions per observation where mentioned."""


@dataclass(frozen=True, slots=True)
class GEODatasetMetrics:
    """Dataset-wide GEO aggregate metrics."""

    dataset_id: str
    total_keywords: int
    keywords_target_mentioned: int
    total_observations: int
    total_target_mentions: int
    overall_mention_rate: float
    """Fraction of keywords where target was mentioned at least once (0.0-1.0)."""
    competitor_domain_counts: dict[str, int] = field(default_factory=dict)
    """Count of how often each competitor domain was mentioned."""


@dataclass(frozen=True, slots=True)
class GEOResult:
    """Complete GEO analysis result for a dataset."""

    dataset_id: str
    keyword_metrics: tuple[GEOMetrics, ...]
    dataset_metrics: GEODatasetMetrics


__all__ = [
    "EntityMention",
    "EntityType",
    "GEODatasetMetrics",
    "GEOMetrics",
    "GEOObservation",
    "GEOResult",
    "GenerativeEngineType",
]
