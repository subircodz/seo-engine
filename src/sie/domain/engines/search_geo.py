"""Generative Engine Optimization (GEO) analytics engine — deterministic (Phase 6N-G).

Pure functions transforming ``GEOObservation`` records into repeatable
GEO metrics.  No I/O, no network, no LLM.  Same input always yields the
same output.

Interpretations:
- Target mention rate is computed across all observations for each keyword.
- Competitor mention counts are aggregated deterministically.
- Entity mention analysis is keyword-scoped.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from sie.domain.models.search_geo import (
    GEODatasetMetrics,
    GEOMetrics,
    GEOObservation,
    GEOResult,
)

__all__ = [
    "analyze_geo_observations",
    "calculate_geo_dataset_metrics",
    "calculate_geo_keyword_metrics",
]


def _group_by_keyword(
    observations: tuple[GEOObservation, ...],
) -> dict[str, list[GEOObservation]]:
    """Group observations by keyword preserving input order."""
    grouped: dict[str, list[GEOObservation]] = defaultdict(list)
    for obs in observations:
        grouped[obs.keyword].append(obs)
    return dict(grouped)


def calculate_geo_keyword_metrics(
    observations: tuple[GEOObservation, ...],
) -> list[GEOMetrics]:
    """Per-keyword GEO aggregates, deterministically sorted by keyword."""
    grouped = _group_by_keyword(observations)
    metrics: list[GEOMetrics] = []

    for keyword in sorted(grouped):
        obs_list = grouped[keyword]
        count = len(obs_list)
        mentioned_count = sum(1 for o in obs_list if o.target_mentioned)
        comp_mentioned = sum(1 for o in obs_list if o.competitor_domains and o.target_mentioned)

        mention_rate = round(mentioned_count / count, 4) if count else 0.0
        avg_mentions = (
            round(
                sum(o.mention_count for o in obs_list if o.target_mentioned) / mentioned_count,
                2,
            )
            if mentioned_count
            else 0.0
        )

        metrics.append(
            GEOMetrics(
                keyword=keyword,
                observation_count=count,
                target_mentioned_count=mentioned_count,
                competitor_mentioned_count=comp_mentioned,
                mention_rate=mention_rate,
                avg_mention_count=avg_mentions,
            )
        )

    return metrics


def calculate_geo_dataset_metrics(
    dataset_id: str,
    observations: tuple[GEOObservation, ...],
    total_keywords: int,
) -> GEODatasetMetrics:
    """Dataset-wide GEO aggregates."""
    keyword_metrics = calculate_geo_keyword_metrics(observations)

    keywords_mentioned = sum(1 for km in keyword_metrics if km.target_mentioned_count > 0)
    total_observations = len(observations)
    total_mentions = sum(km.target_mentioned_count for km in keyword_metrics)

    overall_mention_rate = round(keywords_mentioned / total_keywords, 4) if total_keywords else 0.0

    # Count competitor domain mentions
    comp_counts: Counter[str] = Counter()
    for obs in observations:
        for domain in obs.competitor_domains:
            comp_counts[domain] += 1

    return GEODatasetMetrics(
        dataset_id=dataset_id,
        total_keywords=total_keywords,
        keywords_target_mentioned=keywords_mentioned,
        total_observations=total_observations,
        total_target_mentions=total_mentions,
        overall_mention_rate=overall_mention_rate,
        competitor_domain_counts=dict(comp_counts.most_common()),
    )


def analyze_geo_observations(
    dataset_id: str,
    observations: tuple[GEOObservation, ...],
    total_keywords: int,
) -> GEOResult:
    """Full deterministic GEO analysis composing all metric calculations."""
    keyword_metrics = tuple(calculate_geo_keyword_metrics(observations))
    dataset_metrics = calculate_geo_dataset_metrics(dataset_id, observations, total_keywords)
    return GEOResult(
        dataset_id=dataset_id,
        keyword_metrics=keyword_metrics,
        dataset_metrics=dataset_metrics,
    )
