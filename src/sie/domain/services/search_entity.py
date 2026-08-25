"""Entity Intelligence Service (Phase 8).

Orchestrates the Entity Intelligence engine through the
deterministic analysis pipeline.
"""

from __future__ import annotations

from sie.domain.engines.search_entity import (
    analyze_entity_visibility,
    detect_entity_gaps,
    extract_entities_from_content,
)
from sie.domain.models.search_entity import (
    EntityDatasetResult,
    EntityGap,
    EntitySignal,
)

__all__ = ["EntityIntelligenceService"]


class EntityIntelligenceService:
    """Service for entity extraction, visibility analysis, and gap detection."""

    def extract_entities(self, text: str, **kwargs) -> tuple[EntitySignal, ...]:
        """Extract entities from content text."""
        return extract_entities_from_content(text, **kwargs)

    def analyze_visibility(
        self,
        observations: tuple[dict, ...],
        target_domain: str = "",
    ) -> EntityDatasetResult:
        """Analyze entity visibility across observations."""
        return analyze_entity_visibility(observations, target_domain)

    def detect_gaps(
        self,
        target_entities: tuple[EntitySignal, ...],
        competitor_entities: tuple[EntitySignal, ...],
        **kwargs,
    ) -> tuple[EntityGap, ...]:
        """Detect entity gaps between target and competitors."""
        return detect_entity_gaps(target_entities, competitor_entities, **kwargs)
