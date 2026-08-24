"""Ranking volatility detection (Phase 6N-D)."""

from __future__ import annotations

from dataclasses import dataclass

from sie.domain.models.search import RankingObservation


def _calculate_rankings_volatility(observations: tuple[RankingObservation, ...]) -> float:
    """Calculate ranking volatility for a keyword's observations.

    Volatility is computed as the average absolute position change between consecutive
    observations (ordered by observed_at), normalized by position magnitude.

    Formula: volatility = Σ(|Δposition|) / (Σ(|position|) + 1)

    This produces:
    - 0.0 when there is only one observation (single-observation keywords)
    - Higher values for larger or more frequent position changes
    - Values in [0, 1], where 1 represents extreme volatility

    Returns 0.0 when there are fewer than two observations.
    """
    if len(observations) < 2:
        return 0.0

    positions = [obs.position for obs in sorted(observations, key=lambda o: o.observed_at)]
    volatility = 0.0

    for i in range(1, len(positions)):
        position_change = abs(positions[i] - positions[i - 1])
        volatility += position_change

    total_position_magnitude = sum(abs(p) for p in positions)
    return volatility / (total_position_magnitude + 1)


@dataclass(frozen=True, slots=True)
class RankingVolatilityMetrics:
    """Aggregated volatility metrics for a keyword.

    Contains the raw volatility score and derived severity classification.
    """

    keyword: str
    volatility: float
    severity: str

    def __post_init__(self) -> None:
        if self.volatility < 0:
            raise ValueError(f"volatility must be >= 0, got {self.volatility}")

        if not isinstance(self.severity, str) or not self.severity:
            raise ValueError("severity must be a non-empty string")


class RankingVolatilityService:
    """Domain service for calculating ranking volatility metrics.

    This service implements Phase 6N-D volatility analysis, which provides
    insights into how unstable a keyword's rankings have been over time.

    Key principles:
    - Stable rankings produce low/zero volatility
    - Large position changes produce higher volatility
    - Single-observation keywords must not fabricate volatility
    - Deterministic output based on chronological ordering
    - Original observations are never mutated
    """

    def calculate_volatility_by_keyword(
        self,
        observations: tuple[RankingObservation, ...],
    ) -> tuple[RankingVolatilityMetrics, ...]:
        """Calculate volatility for each keyword.

        Groups observations by keyword, sorts each group by observed_at
        (chronological), and applies the volatility formula to each group.
        """
        # Group observations by keyword
        observations_by_keyword: dict[str, list[RankingObservation]] = {}
        for obs in observations:
            key = obs.keyword
            if key not in observations_by_keyword:
                observations_by_keyword[key] = []
            observations_by_keyword[key].append(obs)

        results: list[RankingVolatilityMetrics] = []
        for keyword, obs_list in observations_by_keyword.items():
            metrics = self._calculate_for_keyword(keyword, obs_list)
            results.append(metrics)

        # Return in sorted order for deterministic output
        return tuple(sorted(results, key=lambda m: m.keyword))

    def _calculate_for_keyword(
        self, keyword: str, observations: list[RankingObservation]
    ) -> RankingVolatilityMetrics:
        volatility = _calculate_rankings_volatility(tuple(observations))
        severity = self._classify_severity(volatility)
        return RankingVolatilityMetrics(
            keyword=keyword,
            volatility=volatility,
            severity=severity,
        )

    def _classify_severity(self, volatility: float) -> str:
        """Classify volatility into severity categories."""
        if volatility < 0.01:
            return "low"
        elif volatility < 0.1:
            return "medium"
        elif volatility < 1.0:
            return "high"
        else:
            return "extreme"

    def get_volatile_keywords(
        self,
        observations: tuple[RankingObservation, ...],
        threshold: float = 0.1,
    ) -> tuple[str, ...]:
        """Return keywords whose volatility exceeds the threshold.

        Useful for identifying keywords with unstable rankings that may need
        investigation or intervention.
        """
        volatility_by_keyword = self.calculate_volatility_by_keyword(observations)
        volatile_keywords = [m.keyword for m in volatility_by_keyword if m.volatility >= threshold]
        return tuple(sorted(volatile_keywords))


__all__ = [
    "RankingVolatilityMetrics",
    "RankingVolatilityService",
]
