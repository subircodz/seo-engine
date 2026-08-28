"""Common search-surface and evidence-provenance models.

SEO, AIO, and GEO are first-class visibility surfaces.  Evidence provenance is
kept separate from the surface/engine identity so an LLM simulation can never
be mistaken for a live observation from the engine it imitates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SearchSurface(StrEnum):
    SEO = "seo"
    AIO = "aio"
    GEO = "geo"


class SurfaceStatus(StrEnum):
    ASSESSED = "assessed"
    NOT_ASSESSED = "not_assessed"
    INSUFFICIENT_DATA = "insufficient_data"
    COLLECTION_FAILED = "collection_failed"
    STALE = "stale"


class ObservationKind(StrEnum):
    """How an observation was obtained.

    ``LIVE_PROVIDER`` means the named provider actually queried the named
    search/generative surface. ``LLM_SIMULATION`` means a model was asked to
    emulate/analyse an engine and is therefore not evidence of that engine's
    live result.
    """

    LIVE_PROVIDER = "live_provider"
    LLM_SIMULATION = "llm_simulation"
    IMPORTED = "imported"
    MANUAL = "manual"
    DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    """Immutable provenance attached to externally observed evidence."""

    provider_name: str
    observation_kind: ObservationKind
    provider_request_id: str | None = None
    retrieved_at: datetime | None = None
    source_url: str | None = None
    methodology: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("provider_name must be non-empty")
        if self.source_url is not None and not self.source_url.strip():
            raise ValueError("source_url cannot be empty when supplied")


@dataclass(frozen=True, slots=True)
class SurfaceAssessment:
    """Evidence-backed summary for one search visibility surface."""

    surface: SearchSurface
    status: SurfaceStatus
    score: float | None
    score_basis: str
    observation_count: int
    data_source: str
    observed_at: datetime | None = None
    freshness_seconds: float | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.score is not None and not 0.0 <= self.score <= 100.0:
            raise ValueError("score must be between 0 and 100")
        if self.observation_count < 0:
            raise ValueError("observation_count cannot be negative")
        if self.freshness_seconds is not None and self.freshness_seconds < 0:
            raise ValueError("freshness_seconds cannot be negative")
        if self.status != SurfaceStatus.ASSESSED and self.score is not None:
            raise ValueError("unassessed surfaces must not expose a numeric score")


@dataclass(frozen=True, slots=True)
class UnifiedSearchVisibility:
    """Unified SEO/AIO/GEO visibility envelope."""

    assessments: tuple[SurfaceAssessment, ...]
    aggregate_score: float | None
    aggregate_methodology: str
    generated_at: datetime

    def __post_init__(self) -> None:
        surfaces = {assessment.surface for assessment in self.assessments}
        if surfaces != {SearchSurface.SEO, SearchSurface.AIO, SearchSurface.GEO}:
            raise ValueError("UnifiedSearchVisibility requires SEO, AIO, and GEO assessments")
        if self.aggregate_score is not None and not 0.0 <= self.aggregate_score <= 100.0:
            raise ValueError("aggregate_score must be between 0 and 100")

    @property
    def assessed_surfaces(self) -> tuple[SurfaceAssessment, ...]:
        return tuple(a for a in self.assessments if a.status == SurfaceStatus.ASSESSED)

    @property
    def unavailable_surfaces(self) -> tuple[SurfaceAssessment, ...]:
        return tuple(a for a in self.assessments if a.status != SurfaceStatus.ASSESSED)


__all__ = [
    "EvidenceProvenance",
    "ObservationKind",
    "SearchSurface",
    "SurfaceAssessment",
    "SurfaceStatus",
    "UnifiedSearchVisibility",
]
