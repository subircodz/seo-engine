"""Common search-surface models for SEO, AIO, and GEO intelligence.

The product treats traditional search visibility, AI Overview visibility, and
Generative Engine visibility as three first-class surfaces over one shared
intelligence foundation.  These models make availability/freshness explicit
so an unavailable surface can never be mistaken for a measured zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class SearchSurface(StrEnum):
    """First-class visibility surfaces supported by the engine."""

    SEO = "seo"
    AIO = "aio"
    GEO = "geo"


class SurfaceStatus(StrEnum):
    """Evidence state of a search-surface assessment."""

    ASSESSED = "assessed"
    NOT_ASSESSED = "not_assessed"
    INSUFFICIENT_DATA = "insufficient_data"
    COLLECTION_FAILED = "collection_failed"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class SurfaceAssessment:
    """Evidence-backed summary for one search visibility surface.

    ``score`` is ``None`` whenever the surface has not been meaningfully
    assessed.  A genuine measured zero therefore remains distinguishable from
    an unavailable surface.
    """

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
    """Unified SEO/AIO/GEO visibility envelope.

    The aggregate score is intentionally optional.  When present, it is the
    normalized mean of *assessed* surfaces only; unavailable surfaces are not
    treated as zero and do not dilute the result.
    """

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
    "SearchSurface",
    "SurfaceAssessment",
    "SurfaceStatus",
    "UnifiedSearchVisibility",
]
