"""Optimization Intelligence domain models (Phase 8).

Immutable value objects for cross-engine synthesis — combines insights
from all intelligence engines into prioritised, actionable SEO optimization
recommendations with impact, effort, and priority scoring.

These models are provider-neutral and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class OptimizationCategory(StrEnum):
    """Categories of SEO optimization recommendations."""

    CONTENT = "content"
    TECHNICAL = "technical"
    AUTHORITY = "authority"
    VISIBILITY = "visibility"
    PERFORMANCE = "performance"
    ENTITY = "entity"
    SERP_FEATURE = "serp_feature"
    AIO = "aio"
    GEO = "geo"
    CANNIBALIZATION = "cannibalization"
    KEYWORD = "keyword"
    COMPETITOR = "competitor"


class OptimizationImpact(StrEnum):
    """Expected impact level of an optimization."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OptimizationEffort(StrEnum):
    """Estimated effort required for an optimization."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class OptimizationRecommendation:
    """A single actionable optimization recommendation."""

    category: OptimizationCategory
    """Which area of SEO this recommendation addresses."""

    title: str
    """Short, actionable title."""

    description: str
    """Detailed description of the recommended action."""

    impact: OptimizationImpact
    """Expected impact if implemented."""

    effort: OptimizationEffort
    """Estimated effort to implement."""

    priority_score: float = 0.0
    """Computed priority score (0.0-1.0, higher = prioritise first).

    Derived deterministically from impact and effort:
    high-impact + low-effort = highest score.
    """

    affected_keywords: tuple[str, ...] = ()
    """Keywords affected by this recommendation."""

    affected_urls: tuple[str, ...] = ()
    """URLs affected by this recommendation."""

    affected_domains: tuple[str, ...] = ()
    """Domains affected (for competitor-related recommendations)."""

    supporting_metrics: dict[str, object] = field(default_factory=dict)
    """Key metrics supporting this recommendation."""

    confidence: float = 0.5
    """Confidence in this recommendation (0.0-1.0)."""

    source_engine: str = ""
    """Which intelligence engine produced this recommendation."""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if not 0.0 <= self.priority_score <= 1.0:
            raise ValueError(f"priority_score must be in [0.0, 1.0], got {self.priority_score}")


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Complete cross-engine optimization synthesis result."""

    dataset_id: str
    recommendations: tuple[OptimizationRecommendation, ...] = ()
    total_recommendations: int = 0
    recommendations_by_category: dict[str, int] = field(default_factory=dict)
    recommendations_by_impact: dict[str, int] = field(default_factory=dict)
    high_priority_count: int = 0
    """Number of recommendations with priority_score >= 0.7."""
    estimated_quick_wins: int = 0
    """Number of high-impact, low-effort recommendations."""
    summary: str = ""
    """Executive summary of the optimization analysis."""


# Priority scoring constants
_IMPACT_WEIGHTS = {
    OptimizationImpact.HIGH: 1.0,
    OptimizationImpact.MEDIUM: 0.6,
    OptimizationImpact.LOW: 0.3,
}

_EFFORT_WEIGHTS = {
    OptimizationEffort.LOW: 1.0,
    OptimizationEffort.MEDIUM: 0.6,
    OptimizationEffort.HIGH: 0.3,
}


def calculate_priority_score(impact: OptimizationImpact, effort: OptimizationEffort) -> float:
    """Deterministic priority score from impact and effort.

    High impact + low effort = 1.0 (highest priority)
    Low impact + high effort = 0.09 (lowest priority)
    """
    impact_w = _IMPACT_WEIGHTS[impact]
    effort_w = _EFFORT_WEIGHTS[effort]
    return round(impact_w * effort_w, 2)


__all__ = [
    "OptimizationCategory",
    "OptimizationEffort",
    "OptimizationImpact",
    "OptimizationRecommendation",
    "OptimizationResult",
    "calculate_priority_score",
]
