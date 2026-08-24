"""Search Analytics Engine — deterministic ranking analysis (Phase 6G).

Pure functions transforming persisted ``RankingObservation`` /
``CompetitorRanking`` records into repeatable SEO metrics.  No I/O, no
network, no LLM.  Same input always yields the same output.

Interpretations (deliberate, documented):

- Position 1 is best; positions are integers >= 1 (guaranteed upstream by
  the Phase 6A model invariants — this engine never fabricates or repairs
  values).
- Observations are grouped per keyword (exact string match on
  ``observation.keyword``, which import normalization already casefolded).
- Within a keyword, observations are ordered by ``observed_at`` using a
  *stable* sort: records sharing a timestamp keep their input order, which
  makes first/latest selection deterministic for any given input sequence.
- Ranking buckets are disjoint bands — Top 3: 1-3, Top 10: 4-10,
  Top 20: 11-20, Top 50: 21-50, Outside Top 50: 51+ — but the reported
  ``top_N_count`` dataset metrics are cumulative counts of keywords whose
  *latest* observation falls within positions 1..N (standard SEO meaning of
  "ranking in the top N").  Each keyword counts once, via its latest
  observation.
- Dataset-level ``average_position`` / ``median_position`` explicitly
  represent observations: computed across every stored observation.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from sie.domain.models.search import CompetitorRanking, RankingObservation, SearchDataset
from sie.domain.models.search_analytics import (
    CompetitorMetrics,
    DatasetSearchMetrics,
    KeywordRankingMetrics,
    SearchAnalyticsResult,
)

__all__ = [
    "analyze_search_dataset",
    "calculate_competitor_metrics",
    "calculate_dataset_metrics",
    "calculate_keyword_metrics",
    "calculate_visibility_score",
]

# ── visibility weight table ───────────────────────────────────────────────
# Deterministic step function over the latest position of each keyword:
#
#     position 1-3   -> 1.00
#     position 4-10  -> 0.70
#     position 11-20 -> 0.40
#     position 21-50 -> 0.15
#     position >50   -> 0.00
#
# score = sum(keyword weights) / number of ranked keywords   (0.0 if empty)


def _visibility_weight(position: int) -> float:
    """Weight for one position, per the documented step function."""
    if position <= 3:
        return 1.00
    if position <= 10:
        return 0.70
    if position <= 20:
        return 0.40
    if position <= 50:
        return 0.15
    return 0.00


def _group_by_keyword(
    observations: tuple[RankingObservation, ...] | list[RankingObservation],
) -> dict[str, list[RankingObservation]]:
    """Group observations by keyword preserving input order within groups."""
    grouped: dict[str, list[RankingObservation]] = defaultdict(list)
    for obs in observations:
        grouped[obs.keyword].append(obs)
    return dict(grouped)


def _ordered(observations: list[RankingObservation]) -> list[RankingObservation]:
    """Chronological order by observed_at; stable for identical timestamps."""
    return sorted(observations, key=lambda obs: obs.observed_at)


def _latest_by_keyword(
    observations: tuple[RankingObservation, ...] | list[RankingObservation],
) -> dict[str, int]:
    """Latest position per keyword, keyed by normalized keyword string."""
    latest: dict[str, int] = {}
    for keyword, group in _group_by_keyword(observations).items():
        ordered = _ordered(group)
        latest[keyword] = ordered[-1].position
    return latest


# ── public engine functions ───────────────────────────────────────────────


def calculate_keyword_metrics(
    observations: tuple[RankingObservation, ...],
) -> list[KeywordRankingMetrics]:
    """Per-keyword aggregates, deterministically sorted by keyword."""
    grouped = _group_by_keyword(observations)
    metrics: list[KeywordRankingMetrics] = []
    for keyword in sorted(grouped):
        ordered = _ordered(grouped[keyword])
        positions = [obs.position for obs in ordered]
        count = len(positions)
        change: int | None = None
        improved = False
        declined = False
        if count >= 2:
            # positive = improvement (first - latest), never inferred from a
            # single observation.
            change = positions[0] - positions[-1]
            improved = change > 0
            declined = change < 0
        metrics.append(
            KeywordRankingMetrics(
                keyword=keyword,
                observation_count=count,
                best_position=min(positions),
                worst_position=max(positions),
                average_position=round(sum(positions) / count, 2),
                latest_position=positions[-1],
                first_position=positions[0],
                position_change=change,
                improved=improved,
                declined=declined,
            )
        )
    return metrics


def calculate_visibility_score(observations: tuple[RankingObservation, ...]) -> float:
    """Mean visibility weight across ranked keywords (latest observation).

    Returns 0.0 when there are no observations.
    """
    latest = _latest_by_keyword(observations)
    if not latest:
        return 0.0
    total = sum(_visibility_weight(position) for position in latest.values())
    return round(total / len(latest), 4)


def calculate_dataset_metrics(
    dataset: SearchDataset,
    observations: tuple[RankingObservation, ...],
) -> DatasetSearchMetrics:
    """Dataset-wide aggregates (see module docstring for interpretations)."""
    latest = _latest_by_keyword(observations)
    positions = [obs.position for obs in observations]
    average = round(sum(positions) / len(positions), 2) if positions else None
    median = round(float(statistics.median(positions)), 2) if positions else None

    top_3 = sum(1 for p in latest.values() if p <= 3)
    top_10 = sum(1 for p in latest.values() if p <= 10)
    top_20 = sum(1 for p in latest.values() if p <= 20)
    top_50 = sum(1 for p in latest.values() if p <= 50)

    keywords_with_rankings = len(latest)
    keywords_not_ranking = max(dataset.total_keywords - keywords_with_rankings, 0)

    return DatasetSearchMetrics(
        dataset_id=dataset.dataset_id,
        total_keywords=dataset.total_keywords,
        total_observations=len(observations),
        keywords_with_rankings=keywords_with_rankings,
        keywords_not_ranking=keywords_not_ranking,
        average_position=average,
        median_position=median,
        top_3_count=top_3,
        top_10_count=top_10,
        top_20_count=top_20,
        top_50_count=top_50,
        visibility_score=calculate_visibility_score(observations),
    )


def calculate_competitor_metrics(
    observations: tuple[RankingObservation, ...],
    competitor_rankings: tuple[CompetitorRanking, ...],
) -> list[CompetitorMetrics]:
    """Per-domain competitor aggregates, deterministically sorted by domain.

    Comparison rule: every competitor record is compared against our site's
    *latest* observation for the same keyword.  Competitor records whose
    keyword has no observation on our side are skipped (nothing invented);
    equal positions count as neither outranking nor outranked.
    """
    our_latest = _latest_by_keyword(observations)
    grouped: dict[str, list[CompetitorRanking]] = defaultdict(list)
    for comp in competitor_rankings:
        grouped[comp.competitor_domain].append(comp)

    metrics: list[CompetitorMetrics] = []
    for domain in sorted(grouped):
        records = grouped[domain]
        positions = [rec.position for rec in records]
        outranking = 0
        outranked = 0
        for rec in records:
            ours = our_latest.get(rec.keyword)
            if ours is None:
                continue  # no comparable observation — skip, do not invent
            if rec.position < ours:
                outranking += 1
            elif rec.position > ours:
                outranked += 1
        metrics.append(
            CompetitorMetrics(
                competitor_domain=domain,
                keyword_count=len({rec.keyword for rec in records}),
                observed_count=len(records),
                average_position=round(sum(positions) / len(positions), 2),
                top_10_count=sum(1 for p in positions if p <= 10),
                outranking_count=outranking,
                outranked_count=outranked,
            )
        )
    return metrics


def analyze_search_dataset(
    dataset: SearchDataset,
    observations: tuple[RankingObservation, ...],
    competitor_rankings: tuple[CompetitorRanking, ...],
) -> SearchAnalyticsResult:
    """Full deterministic analysis composing all metric calculations."""
    keyword_metrics = tuple(calculate_keyword_metrics(observations))
    dataset_metrics = calculate_dataset_metrics(dataset, observations)
    competitor_metrics = tuple(calculate_competitor_metrics(observations, competitor_rankings))
    return SearchAnalyticsResult(
        dataset_id=dataset.dataset_id,
        keyword_metrics=keyword_metrics,
        dataset_metrics=dataset_metrics,
        competitor_metrics=competitor_metrics,
    )
