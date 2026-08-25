"""Optimization Intelligence Service (Phase 8).

Orchestrates the cross-engine optimization synthesis.
"""

from __future__ import annotations

from sie.domain.engines.search_optimization import (
    synthesize_optimization_recommendations,
)
from sie.domain.models.search_optimization import OptimizationResult

__all__ = ["OptimizationIntelligenceService"]


class OptimizationIntelligenceService:
    """Service for cross-engine optimization synthesis."""

    def synthesize(self, dataset_id: str, **kwargs) -> OptimizationResult:
        """Synthesise optimization recommendations from all intelligence inputs."""
        return synthesize_optimization_recommendations(dataset_id, **kwargs)
