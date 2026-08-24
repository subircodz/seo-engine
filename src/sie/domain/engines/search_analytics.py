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
from sie.domain.models.search_serp import SERPFeatureType

__all__ = [
    "analyze_search_dataset",
    "calculate_competitor_metrics",
    "calculate_dataset_metrics",
    "calculate_keyword_metrics",
    "calculate_serp_feature_metrics",
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

    # Derive target domain from observations for ownership detection
    target_domain = _derive_target_domain(observations)

    (
        total_occurrences,
        obs_with_features,
        fs_count,
        paa_count,
        fs_owned,
        paa_owned,
        kw_fs,
        kw_paa,
    ) = _serp_feature_metrics_for_dataset(observations, target_domain)

    serp_features_by_type = calculate_serp_feature_metrics(observations, target_domain)

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
        total_serp_feature_occurrences=total_occurrences,
        serp_features_by_type=serp_features_by_type,
        observations_with_serp_features=obs_with_features,
        featured_snippet_occurrences=fs_count,
        people_also_ask_occurrences=paa_count,
        featured_snippet_owned_by_target=fs_owned,
        people_also_ask_owned_by_target=paa_owned,
        keywords_with_featured_snippet=kw_fs,
        keywords_with_people_also_ask=kw_paa,
    )


def _derive_target_domain(
    observations: tuple[RankingObservation, ...],
) -> str | None:
    """Derive a target domain from the observations' normalized keyword URLs.

    Returns the most common bare domain among target_urls, or None if
    observations are empty.
    """
    if not observations:
        return None
    domains = [_extract_domain_from_url(obs.target_url) for obs in observations]
    from collections import Counter

    return Counter(domains).most_common(1)[0][0]


def _extract_domain_from_url(url: str) -> str:
    """Extract bare, casefolded hostname from URL, stripping www."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = (parsed.netloc or "").split(":")[0].casefold()
    if host.startswith("www."):
        host = host[4:]
    return host


def calculate_serp_feature_metrics(
    observations: tuple[RankingObservation, ...],
    target_domain: str | None = None,
) -> dict[str, int]:
    """Count SERP feature occurrences across all observations.

    Returns a dict mapping feature_type.value to count.
    Only counts features whose domain matches target_domain if provided.
    """
    counts: dict[str, int] = {}
    for obs in observations:
        for feature in obs.serp_features:
            if target_domain is not None and feature.domain != target_domain:
                continue
            feature_type = feature.feature_type.value
            counts[feature_type] = counts.get(feature_type, 0) + 1
    return counts


def _serp_feature_metrics_for_dataset(
    observations: tuple[RankingObservation, ...],
    target_domain: str | None = None,
) -> tuple[int, int, int, int, int, int, int, int]:
    """Calculate SERP feature metrics for dataset-level aggregation.

    Returns: (total_occurrences, obs_with_features, featured_snippet_count,
              paa_count, featured_snippet_owned, paa_owned, kw_with_fs, kw_with_paa)

    - total_occurrences: sum of all SERP feature instances
    - obs_with_features: number of observations containing at least one feature
    - featured_snippet_count: total featured snippets
    - paa_count: total People Also Ask features
    - featured_snippet_owned: featured snippets where domain matches target_domain
    - paa_owned: PAA where domain matches target_domain
    - kw_with_fs: number of distinct keywords with featured snippets
    - kw_with_paa: number of distinct keywords with PAA

    Ownership is only counted when the SERP feature has an explicit domain
    that matches the target_domain.
    """
    total_occurrences = 0
    obs_with_features = set()
    featured_snippet_count = 0
    paa_count = 0
    featured_snippet_owned = 0
    paa_owned = 0
    kw_with_fs = set()
    kw_with_paa = set()

    for obs in observations:
        has_feature = False
        for feature in obs.serp_features:
            total_occurrences += 1
            has_feature = True

            if target_domain is not None and feature.domain is not None:
                # Feature has explicit domain - check ownership
                if feature.domain == target_domain:
                    if feature.feature_type == SERPFeatureType.FEATURED_SNIPPET:
                        featured_snippet_count += 1
                        kw_with_fs.add(obs.keyword)
                        featured_snippet_owned += 1
                    elif feature.feature_type == SERPFeatureType.PEOPLE_ALSO_ASK:
                        paa_count += 1
                        kw_with_paa.add(obs.keyword)
                        paa_owned += 1
                elif feature.feature_type == SERPFeatureType.FEATURED_SNIPPET:
                    featured_snippet_count += 1
                    kw_with_fs.add(obs.keyword)
                elif feature.feature_type == SERPFeatureType.PEOPLE_ALSO_ASK:
                    paa_count += 1
                    kw_with_paa.add(obs.keyword)
            else:
                # No domain on feature - just count occurrences
                if feature.feature_type == SERPFeatureType.FEATURED_SNIPPET:
                    featured_snippet_count += 1
                    kw_with_fs.add(obs.keyword)
                elif feature.feature_type == SERPFeatureType.PEOPLE_ALSO_ASK:
                    paa_count += 1
                    kw_with_paa.add(obs.keyword)

        if has_feature:
            obs_with_features.add(obs.keyword)

    return (
        total_occurrences,
        len(obs_with_features),
        featured_snippet_count,
        paa_count,
        featured_snippet_owned,
        paa_owned,
        len(kw_with_fs),
        len(kw_with_paa),
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
