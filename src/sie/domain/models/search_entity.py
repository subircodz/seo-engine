"""Entity Intelligence domain models (Phase 8).

Immutable value objects representing entity/topic signals extracted from
content and search data.  Captures entity frequency, topic clustering,
entity visibility, and competitor entity gaps.

These models are provider-neutral and deterministic — entity extraction
uses deterministic heuristics, never LLM or NLP dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EntityCategory(StrEnum):
    """Categories of entities detectable from content."""

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    PRODUCT = "product"
    BRAND = "brand"
    CONCEPT = "concept"
    DATE_REFERENCE = "date_reference"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class EntitySignal:
    """A single detected entity from content analysis.

    Entities are extracted using deterministic heuristics (capitalized
    multi-word phrases, known patterns, frequency analysis) without
    external NLP dependencies.
    """

    text: str
    """The entity text as detected in content."""

    category: EntityCategory = EntityCategory.OTHER
    """Category of entity."""

    frequency: int = 1
    """Number of times this entity appears in the analyzed text."""

    is_target: bool = False
    """Whether this entity refers to the tracked target brand/domain."""

    domain: str = ""
    """Associated domain, if the entity maps to a web entity."""

    confidence: float = 0.5
    """Detection confidence (0.0-1.0)."""

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("text must be a non-empty string")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {self.confidence}"
            )
        if self.frequency < 1:
            raise ValueError(f"frequency must be >= 1, got {self.frequency}")


@dataclass(frozen=True, slots=True)
class TopicCluster:
    """A group of related entities forming a topic cluster.

    Topics are derived from entity co-occurrence patterns within
    content, using deterministic grouping.
    """

    topic_label: str
    """Descriptive label for this topic cluster."""

    entities: tuple[EntitySignal, ...] = ()
    """Entities belonging to this cluster."""

    relevance_score: float = 0.0
    """Relevance score (0.0-1.0) based on entity frequency and co-occurrence."""

    keyword: str = ""
    """Associated keyword/query, if topic is keyword-scoped."""

    @property
    def entity_count(self) -> int:
        """Number of entities in this cluster."""
        return len(self.entities)

    @property
    def top_entity(self) -> EntitySignal | None:
        """The most frequent entity in this cluster."""
        if not self.entities:
            return None
        return max(self.entities, key=lambda e: e.frequency)


@dataclass(frozen=True, slots=True)
class EntityVisibilityResult:
    """Entity visibility analysis result for a single keyword."""

    keyword: str
    """The search query / keyword analyzed."""

    total_entities: int = 0
    """Total unique entities detected."""

    target_entities: tuple[EntitySignal, ...] = ()
    """Entities referring to the target brand/domain."""

    competitor_entities: tuple[EntitySignal, ...] = ()
    """Entities referring to competitors."""

    shared_entities: tuple[str, ...] = ()
    """Entity texts present in both target and competitor content."""

    entity_coverage: float = 0.0
    """Fraction of detected entities that are target-owned (0.0-1.0)."""


@dataclass(frozen=True, slots=True)
class EntityDatasetResult:
    """Dataset-wide entity analysis result."""

    dataset_id: str
    keyword_results: tuple[EntityVisibilityResult, ...] = ()
    total_unique_entities: int = 0
    target_entity_mentions: int = 0
    overall_coverage: float = 0.0
    """Average entity coverage across keywords (0.0-1.0)."""
    topic_clusters: tuple[TopicCluster, ...] = ()
    """Detected topic clusters across the dataset."""


@dataclass(frozen=True, slots=True)
class EntityGap:
    """An entity present in competitor content but missing from target."""

    entity_text: str
    """The missing entity text."""

    entity_category: EntityCategory = EntityCategory.OTHER
    """Category of the missing entity."""

    competitor_frequency: int = 0
    """How often competitors reference this entity."""

    competitor_domains: tuple[str, ...] = ()
    """Competitor domains referencing this entity."""

    recommended_action: str = ""
    """Suggested action to address this entity gap."""


__all__ = [
    "EntityCategory",
    "EntityDatasetResult",
    "EntityGap",
    "EntitySignal",
    "EntityVisibilityResult",
    "TopicCluster",
]
