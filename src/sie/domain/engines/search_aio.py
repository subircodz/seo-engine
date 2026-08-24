"""AI Overview (AIO) analytics engine — deterministic analysis (Phase 6N-F).

Pure functions transforming ``AIOverviewObservation`` records into repeatable
AIO metrics.  No I/O, no network, no LLM.  Same input always yields the
same output.

Interpretations:
- AI overview presence is boolean per observation.
- Target citation rate is computed only over observations where an AI
  overview was actually present (division by zero → 0.0).
- Competitor citation counts are aggregated deterministically.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from sie.domain.models.search_aio import (
    AIOverviewDatasetMetrics,
    AIOverviewMetrics,
    AIOverviewObservation,
    AIOverviewResult,
)

__all__ = [
    "analyze_aio_observations",
    "calculate_aio_dataset_metrics",
    "calculate_aio_keyword_metrics",
]


def _group_by_keyword(
    observations: tuple[AIOverviewObservation, ...],
) -> dict[str, list[AIOverviewObservation]]:
    """Group observations by keyword preserving input order."""
    grouped: dict[str, list[AIOverviewObservation]] = defaultdict(list)
    for obs in observations:
        grouped[obs.keyword].append(obs)
    return dict(grouped)


def calculate_aio_keyword_metrics(
    observations: tuple[AIOverviewObservation, ...],
) -> list[AIOverviewMetrics]:
    """Per-keyword AIO aggregates, deterministically sorted by keyword."""
    grouped = _group_by_keyword(observations)
    metrics: list[AIOverviewMetrics] = []

    for keyword in sorted(grouped):
        obs_list = grouped[keyword]
        count = len(obs_list)
        present_count = sum(1 for o in obs_list if o.present)
        cited_count = sum(1 for o in obs_list if o.target_cited)
        comp_cited = sum(1 for o in obs_list if o.competitor_cited_domains and o.present)

        citation_rate = round(present_count / count, 4) if count else 0.0
        target_citation_rate = round(cited_count / present_count, 4) if present_count else 0.0

        metrics.append(
            AIOverviewMetrics(
                keyword=keyword,
                observation_count=count,
                ai_overview_present_count=present_count,
                target_cited_count=cited_count,
                competitor_cited_count=comp_cited,
                citation_rate=citation_rate,
                target_citation_rate=target_citation_rate,
            )
        )

    return metrics


def calculate_aio_dataset_metrics(
    dataset_id: str,
    observations: tuple[AIOverviewObservation, ...],
    total_keywords: int,
) -> AIOverviewDatasetMetrics:
    """Dataset-wide AIO aggregates."""
    keyword_metrics = calculate_aio_keyword_metrics(observations)

    keywords_with_ai = sum(1 for km in keyword_metrics if km.ai_overview_present_count > 0)
    keywords_target_cited = sum(1 for km in keyword_metrics if km.target_cited_count > 0)
    total_ai_obs = sum(km.ai_overview_present_count for km in keyword_metrics)
    total_citations = sum(km.target_cited_count for km in keyword_metrics)

    target_citation_rate = (
        round(keywords_target_cited / keywords_with_ai, 4) if keywords_with_ai else 0.0
    )

    # Collect all unique competitor cited domains
    all_comp_domains: Counter[str] = Counter()
    for obs in observations:
        if obs.present:
            for domain in obs.competitor_cited_domains:
                all_comp_domains[domain] += 1

    return AIOverviewDatasetMetrics(
        dataset_id=dataset_id,
        total_keywords=total_keywords,
        keywords_with_ai_overview=keywords_with_ai,
        keywords_target_cited=keywords_target_cited,
        total_ai_overview_observations=total_ai_obs,
        total_citations=total_citations,
        target_citation_rate=target_citation_rate,
        competitor_cited_domains=tuple(d for d, _ in all_comp_domains.most_common()),
    )


def analyze_aio_observations(
    dataset_id: str,
    observations: tuple[AIOverviewObservation, ...],
    total_keywords: int,
) -> AIOverviewResult:
    """Full deterministic AIO analysis composing all metric calculations."""
    keyword_metrics = tuple(calculate_aio_keyword_metrics(observations))
    dataset_metrics = calculate_aio_dataset_metrics(dataset_id, observations, total_keywords)
    return AIOverviewResult(
        dataset_id=dataset_id,
        keyword_metrics=keyword_metrics,
        dataset_metrics=dataset_metrics,
    )
