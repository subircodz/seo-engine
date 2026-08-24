"""Search analytics result models (Phase 6G).

Immutable value objects produced by the deterministic ``search_analytics``
engine.  Every metric is derived purely from stored observations — nothing is
fabricated, no network, no LLM.  Same input always yields the same output.

Conventions shared with Phase 6A:

- ``frozen=True, slots=True`` dataclasses; instances are never mutated.
- Positions are integers >= 1 (1 = best), enforced upstream by the
  ``RankingObservation`` / ``CompetitorRanking`` model invariants.
- Averages are rounded to 2 decimal places, the visibility score to 4;
  rounding keeps API payloads readable without sacrificing determinism.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CompetitorMetrics",
    "DatasetSearchMetrics",
    "KeywordRankingMetrics",
    "SearchAnalyticsResult",
]


@dataclass(frozen=True, slots=True)
class KeywordRankingMetrics:
    """Per-keyword ranking aggregates over all of its observations.

    ``first_position`` / ``latest_position`` are ordered by ``observed_at``
    (input order breaks ties).  ``position_change`` is
    ``first_position - latest_position`` — positive means improvement,
    negative decline.  It is ``None`` when the keyword has fewer than two
    observations: a trend is never inferred from a single data point.
    """

    keyword: str
    observation_count: int
    best_position: int
    worst_position: int
    average_position: float
    latest_position: int
    first_position: int
    position_change: int | None
    improved: bool
    declined: bool


@dataclass(frozen=True, slots=True)
class DatasetSearchMetrics:
    """Dataset-wide aggregates.

    Interpretations (documented deliberately):

    - ``total_keywords`` comes from the dataset metadata (tracked keywords);
      ``keywords_with_rankings`` counts distinct keywords present in the
      observations; ``keywords_not_ranking`` is the non-negative remainder.
    - ``average_position`` / ``median_position`` are computed across *all*
      observations (an observation-level view), ``None`` when there are none.
    - The ``top_*_count`` metrics are *cumulative*: they count keywords whose
      latest observation falls within positions 1..N (top_3 ⊆ top_10 ⊆
      top_20 ⊆ top_50).  Each keyword is represented once, by its latest
      observation.
    - ``visibility_score`` is the mean per-keyword weight of the latest
      observation (see the engine's documented weight table); 0.0 when empty.
    """

    dataset_id: str
    total_keywords: int
    total_observations: int
    keywords_with_rankings: int
    keywords_not_ranking: int
    average_position: float | None
    median_position: float | None
    top_3_count: int
    top_10_count: int
    top_20_count: int
    top_50_count: int
    visibility_score: float

    # SERP Feature Analytics (Phase 6N)
    total_serp_feature_occurrences: int = 0
    serp_features_by_type: dict[str, int] = field(default_factory=dict)
    observations_with_serp_features: int = 0
    featured_snippet_occurrences: int = 0
    people_also_ask_occurrences: int = 0
    featured_snippet_owned_by_target: int = 0
    people_also_ask_owned_by_target: int = 0
    keywords_with_featured_snippet: int = 0
    keywords_with_people_also_ask: int = 0


@dataclass(frozen=True, slots=True)
class CompetitorMetrics:
    """Per-competitor-domain aggregates over its ranking records.

    Unlike the dataset-level ``top_*_count`` metrics (per-keyword latest),
    ``top_10_count`` here explicitly represents *observations*: it counts
    this competitor's ranking records with position <= 10.

    ``outranking_count`` / ``outranked_count`` compare each competitor record
    against our site's *latest* observation for the same keyword.  Records
    without a comparable observation are skipped — never invented.  Equal
    positions count as neither.
    """

    competitor_domain: str
    keyword_count: int
    observed_count: int
    average_position: float
    top_10_count: int
    outranking_count: int
    outranked_count: int


@dataclass(frozen=True, slots=True)
class SearchAnalyticsResult:
    """Complete deterministic analysis of one search dataset."""

    dataset_id: str
    keyword_metrics: tuple[KeywordRankingMetrics, ...]
    dataset_metrics: DatasetSearchMetrics
    competitor_metrics: tuple[CompetitorMetrics, ...]
