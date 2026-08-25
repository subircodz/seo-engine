"""Consolidated Intelligence Reporting domain models (Phase 8).

Immutable value objects for generating unified intelligence reports that
aggregate all engine outputs into a single structured report with executive
summary, component breakdowns, and prioritised action items.

These models are provider-neutral and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ReportStatus(StrEnum):
    """Status of a report component."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ActionPriority(StrEnum):
    """Priority levels for report action items."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class ReportComponent:
    """One engine's contribution to the consolidated report."""

    name: str
    """Name of the intelligence component (e.g. 'ranking', 'serp_features')."""

    status: ReportStatus
    """Whether this component's analysis was complete, partial, or unavailable."""

    summary: str = ""
    """Brief summary of this component's findings."""

    key_metrics: dict[str, object] = field(default_factory=dict)
    """Key metrics from this component."""

    finding_count: int = 0
    """Number of findings/insights from this component."""

    recommendation_count: int = 0
    """Number of recommendations from this component."""


@dataclass(frozen=True, slots=True)
class ActionItem:
    """A cross-cutting prioritised action item for the consolidated report."""

    order: int
    """Display order (1 = highest priority)."""

    priority: ActionPriority
    """Priority level."""

    title: str
    """Short actionable title."""

    description: str
    """Detailed description of the action."""

    source_components: tuple[str, ...] = ()
    """Which intelligence components contributed to this action."""

    affected_keywords: tuple[str, ...] = ()
    """Keywords affected."""

    affected_urls: tuple[str, ...] = ()
    """URLs affected."""

    effort: str = "medium"
    """Estimated effort: 'low', 'medium', or 'high'."""

    confidence: float = 0.5
    """Confidence in this action item (0.0-1.0)."""


@dataclass(frozen=True, slots=True)
class IntelligenceReport:
    """Consolidated intelligence report across all engines.

    Aggregates all engine outputs into a single structured report
    with executive summary, component breakdown, and prioritised
    action items.
    """

    dataset_id: str
    """Identifier for the dataset this report covers."""

    summary: str
    """Executive summary of all intelligence findings."""

    components: tuple[ReportComponent, ...] = ()
    """Individual engine contributions."""

    action_items: tuple[ActionItem, ...] = ()
    """Prioritised cross-cutting action items."""

    total_findings: int = 0
    """Total findings across all components."""

    total_recommendations: int = 0
    """Total recommendations across all components."""

    generated_at: datetime = field(default_factory=_utc_now)
    """When this report was generated."""

    metadata: dict[str, object] = field(default_factory=dict)
    """Additional metadata (dataset info, engine versions, etc.)."""


__all__ = [
    "ActionItem",
    "ActionPriority",
    "IntelligenceReport",
    "ReportComponent",
    "ReportStatus",
]
