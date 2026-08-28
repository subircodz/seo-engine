"""Generative Engine Optimization (GEO) intelligence domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from sie.domain.models.search_surface import EvidenceProvenance, ObservationKind


def _utc_now() -> datetime:
    return datetime.now(UTC)


class GenerativeEngineType(StrEnum):
    GOOGLE_AI_OVERVIEW = "google_ai_overview"
    BING_COPILOT = "bing_copilot"
    PERPLEXITY = "perplexity"
    CHATGPT = "chatgpt"
    CLAUDE = "claude"
    GEMINI = "gemini"
    OTHER = "other"


class EntityType(StrEnum):
    BRAND = "brand"
    PRODUCT = "product"
    PERSON = "person"
    LOCATION = "location"
    ORGANIZATION = "organization"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class EntityMention:
    text: str
    entity_type: EntityType = EntityType.BRAND
    is_target: bool = False
    domain: str = ""

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("text must be a non-empty string")


@dataclass(frozen=True, slots=True)
class GEOObservation:
    """One generative-search observation with explicit engine/evidence identity.

    ``engine_type`` describes the system being measured. ``provenance``
    describes how it was measured. Therefore a CHATGPT engine_type with an
    LLM_SIMULATION provenance is explicitly a simulation, not a live ChatGPT
    observation.
    """

    keyword: str
    engine_type: GenerativeEngineType
    target_mentioned: bool = False
    target_domain: str = ""
    mention_count: int = 0
    entity_mentions: tuple[EntityMention, ...] = ()
    competitor_domains: tuple[str, ...] = ()
    citation_urls: tuple[str, ...] = ()
    answer_length: int = 0
    observed_at: datetime = field(default_factory=_utc_now)
    source: str = "manual"
    provenance: EvidenceProvenance | None = None

    def __post_init__(self) -> None:
        if not self.keyword or not self.keyword.strip():
            raise ValueError("keyword must be a non-empty string")
        object.__setattr__(self, "keyword", " ".join(self.keyword.split()).casefold())
        if self.target_domain:
            object.__setattr__(
                self, "target_domain", self.target_domain.casefold().removeprefix("www.").strip()
            )
        if self.mention_count < 0 or self.answer_length < 0:
            raise ValueError("mention_count and answer_length cannot be negative")
        if self.provenance is None:
            object.__setattr__(
                self,
                "provenance",
                EvidenceProvenance(
                    provider_name=self.source,
                    observation_kind=ObservationKind.MANUAL,
                    retrieved_at=self.observed_at,
                ),
            )


@dataclass(frozen=True, slots=True)
class GEOMetrics:
    keyword: str
    observation_count: int
    target_mentioned_count: int
    competitor_mentioned_count: int
    mention_rate: float
    avg_mention_count: float


@dataclass(frozen=True, slots=True)
class GEODatasetMetrics:
    dataset_id: str
    total_keywords: int
    keywords_target_mentioned: int
    total_observations: int
    total_target_mentions: int
    overall_mention_rate: float
    competitor_domain_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GEOResult:
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
