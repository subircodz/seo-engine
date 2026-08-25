"""Optimization Intelligence engine — cross-engine synthesis (Phase 8).

Pure functions that combine outputs from all intelligence engines into
prioritised, actionable SEO optimization recommendations.

This engine does NOT recalculate underlying analytics — it consumes
existing results and synthesises cross-cutting recommendations.

Priority scoring is deterministic: high impact + low effort ranks first.
"""

from __future__ import annotations

from dataclasses import dataclass

from sie.domain.models.search_optimization import (
    OptimizationCategory,
    OptimizationEffort,
    OptimizationImpact,
    OptimizationRecommendation,
    OptimizationResult,
    calculate_priority_score,
)

__all__ = [
    "synthesize_optimization_recommendations",
]


@dataclass(frozen=True)
class _IntelligenceInputs:
    """Container for all intelligence engine outputs.

    Uses Any-typed fields to avoid circular dependencies — the
    optimization engine consumes results, it doesn't define them.
    """

    # Ranking / analytics
    visibility_score: float = 0.0
    keywords_not_ranking: int = 0
    total_keywords: int = 0
    top_10_count: int = 0
    top_20_count: int = 0

    # SERP features
    featured_snippet_occurrences: int = 0
    featured_snippet_owned: int = 0
    people_also_ask_occurrences: int = 0
    people_also_ask_owned: int = 0
    keywords_with_featured_snippet: int = 0

    # Cannibalization
    cannibalization_count: int = 0
    extreme_cannibalization_count: int = 0

    # Volatility
    volatile_keyword_count: int = 0
    total_volatility_keywords: int = 0

    # Opportunities
    competitor_gap_count: int = 0
    weak_ranking_count: int = 0
    content_gap_count: int = 0
    total_opportunities: int = 0

    # AIO
    aio_keywords_with_overview: int = 0
    aio_target_cited_count: int = 0
    aio_total_keywords: int = 0

    # GEO
    geo_keywords_mentioned: int = 0
    geo_total_keywords: int = 0
    geo_overall_mention_rate: float = 0.0

    # Performance
    avg_performance_score: float = 0.0
    pages_below_threshold: int = 0
    performance_total_pages: int = 0

    # Entity
    entity_coverage: float = 0.0
    entity_gap_count: int = 0

    # Affected data for recommendations
    volatile_keywords: tuple[str, ...] = ()
    competitor_gap_keywords: tuple[str, ...] = ()
    weak_ranking_keywords: tuple[str, ...] = ()
    content_gap_keywords: tuple[str, ...] = ()
    cannibalized_keywords: tuple[str, ...] = ()
    non_ranking_keywords: tuple[str, ...] = ()


def synthesize_optimization_recommendations(
    dataset_id: str,
    *,
    visibility_score: float = 0.0,
    keywords_not_ranking: int = 0,
    total_keywords: int = 0,
    top_10_count: int = 0,
    top_20_count: int = 0,
    featured_snippet_occurrences: int = 0,
    featured_snippet_owned: int = 0,
    people_also_ask_occurrences: int = 0,
    people_also_ask_owned: int = 0,
    keywords_with_featured_snippet: int = 0,
    cannibalization_count: int = 0,
    extreme_cannibalization_count: int = 0,
    volatile_keyword_count: int = 0,
    total_volatility_keywords: int = 0,
    competitor_gap_count: int = 0,
    weak_ranking_count: int = 0,
    content_gap_count: int = 0,
    total_opportunities: int = 0,
    aio_keywords_with_overview: int = 0,
    aio_target_cited_count: int = 0,
    aio_total_keywords: int = 0,
    geo_keywords_mentioned: int = 0,
    geo_total_keywords: int = 0,
    geo_overall_mention_rate: float = 0.0,
    avg_performance_score: float = 0.0,
    pages_below_threshold: int = 0,
    performance_total_pages: int = 0,
    entity_coverage: float = 0.0,
    entity_gap_count: int = 0,
    volatile_keywords: tuple[str, ...] = (),
    competitor_gap_keywords: tuple[str, ...] = (),
    weak_ranking_keywords: tuple[str, ...] = (),
    content_gap_keywords: tuple[str, ...] = (),
    cannibalized_keywords: tuple[str, ...] = (),
    non_ranking_keywords: tuple[str, ...] = (),
) -> OptimizationResult:
    """Synthesise cross-engine optimization recommendations.

    Consumes metrics from all intelligence engines and produces
    prioritised, actionable recommendations.  Does NOT recalculate
    any underlying analytics.

    Priority scoring: high impact x high effort score = highest priority.
    """
    inputs = _IntelligenceInputs(
        visibility_score=visibility_score,
        keywords_not_ranking=keywords_not_ranking,
        total_keywords=total_keywords,
        top_10_count=top_10_count,
        top_20_count=top_20_count,
        featured_snippet_occurrences=featured_snippet_occurrences,
        featured_snippet_owned=featured_snippet_owned,
        people_also_ask_occurrences=people_also_ask_occurrences,
        people_also_ask_owned=people_also_ask_owned,
        keywords_with_featured_snippet=keywords_with_featured_snippet,
        cannibalization_count=cannibalization_count,
        extreme_cannibalization_count=extreme_cannibalization_count,
        volatile_keyword_count=volatile_keyword_count,
        total_volatility_keywords=total_volatility_keywords,
        competitor_gap_count=competitor_gap_count,
        weak_ranking_count=weak_ranking_count,
        content_gap_count=content_gap_count,
        total_opportunities=total_opportunities,
        aio_keywords_with_overview=aio_keywords_with_overview,
        aio_target_cited_count=aio_target_cited_count,
        aio_total_keywords=aio_total_keywords,
        geo_keywords_mentioned=geo_keywords_mentioned,
        geo_total_keywords=geo_total_keywords,
        geo_overall_mention_rate=geo_overall_mention_rate,
        avg_performance_score=avg_performance_score,
        pages_below_threshold=pages_below_threshold,
        performance_total_pages=performance_total_pages,
        entity_coverage=entity_coverage,
        entity_gap_count=entity_gap_count,
        volatile_keywords=volatile_keywords,
        competitor_gap_keywords=competitor_gap_keywords,
        weak_ranking_keywords=weak_ranking_keywords,
        content_gap_keywords=content_gap_keywords,
        cannibalized_keywords=cannibalized_keywords,
        non_ranking_keywords=non_ranking_keywords,
    )

    recs: list[OptimizationRecommendation] = []

    # ── Ranking intelligence recommendations ──
    recs.extend(_ranking_recommendations(inputs))

    # ── Cannibalization recommendations ──
    recs.extend(_cannibalization_recommendations(inputs))

    # ── Volatility recommendations ──
    recs.extend(_volatility_recommendations(inputs))

    # ── SERP feature recommendations ──
    recs.extend(_serp_feature_recommendations(inputs))

    # ── Opportunity recommendations ──
    recs.extend(_opportunity_recommendations(inputs))

    # ── AIO recommendations ──
    recs.extend(_aio_recommendations(inputs))

    # ── GEO recommendations ──
    recs.extend(_geo_recommendations(inputs))

    # ── Performance recommendations ──
    recs.extend(_performance_recommendations(inputs))

    # ── Entity recommendations ──
    recs.extend(_entity_recommendations(inputs))

    # Sort by priority_score descending, then confidence descending
    recs.sort(key=lambda r: (-r.priority_score, -r.confidence))

    # Build summary counts
    by_category: dict[str, int] = {}
    by_impact: dict[str, int] = {}
    for r in recs:
        by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        by_impact[r.impact.value] = by_impact.get(r.impact.value, 0) + 1

    high_priority = sum(1 for r in recs if r.priority_score >= 0.7)
    quick_wins = sum(
        1
        for r in recs
        if r.impact == OptimizationImpact.HIGH and r.effort == OptimizationEffort.LOW
    )

    summary = _build_summary(inputs, len(recs))

    return OptimizationResult(
        dataset_id=dataset_id,
        recommendations=tuple(recs),
        total_recommendations=len(recs),
        recommendations_by_category=by_category,
        recommendations_by_impact=by_impact,
        high_priority_count=high_priority,
        estimated_quick_wins=quick_wins,
        summary=summary,
    )


# ── Individual recommendation builders ────────────────────────────────


def _ranking_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build ranking-related recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.keywords_not_ranking > 0 and inputs.total_keywords > 0:
        pct = inputs.keywords_not_ranking / inputs.total_keywords
        impact = OptimizationImpact.HIGH if pct > 0.3 else OptimizationImpact.MEDIUM
        effort = (
            OptimizationEffort.HIGH
            if inputs.keywords_not_ranking > 50
            else OptimizationEffort.MEDIUM
        )
        score = calculate_priority_score(impact, effort)

        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.KEYWORD,
                title=f"Address {inputs.keywords_not_ranking} non-ranking keywords",
                description=(
                    f"{inputs.keywords_not_ranking} of {inputs.total_keywords} "
                    f"tracked keywords have no current ranking. Review content "
                    f"quality, technical SEO, and backlink profile for these keywords."
                ),
                impact=impact,
                effort=effort,
                priority_score=score,
                affected_keywords=inputs.non_ranking_keywords,
                supporting_metrics={
                    "keywords_not_ranking": inputs.keywords_not_ranking,
                    "total_keywords": inputs.total_keywords,
                },
                confidence=0.9,
                source_engine="ranking",
            )
        )

    if inputs.visibility_score < 0.3 and inputs.total_keywords > 0:
        score = calculate_priority_score(OptimizationImpact.HIGH, OptimizationEffort.HIGH)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.VISIBILITY,
                title="Improve overall visibility score",
                description=(
                    f"Visibility score is {inputs.visibility_score:.2f} "
                    f"(below 0.3). Fundamental improvements needed across "
                    f"content quality, technical SEO, and authority building."
                ),
                impact=OptimizationImpact.HIGH,
                effort=OptimizationEffort.HIGH,
                priority_score=score,
                supporting_metrics={"visibility_score": inputs.visibility_score},
                confidence=0.95,
                source_engine="ranking",
            )
        )

    return recs


def _cannibalization_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build cannibalization-related recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.extreme_cannibalization_count > 0:
        score = calculate_priority_score(OptimizationImpact.HIGH, OptimizationEffort.MEDIUM)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.CANNIBALIZATION,
                title=(
                    f"Resolve {inputs.extreme_cannibalization_count} extreme cannibalization cases"
                ),
                description=(
                    f"{inputs.extreme_cannibalization_count} keywords have extreme "
                    f"cannibalization with multiple competing URLs. Consolidate "
                    f"content, implement canonical tags, or restructure internal linking."
                ),
                impact=OptimizationImpact.HIGH,
                effort=OptimizationEffort.MEDIUM,
                priority_score=score,
                affected_keywords=inputs.cannibalized_keywords,
                supporting_metrics={
                    "extreme_count": inputs.extreme_cannibalization_count,
                    "total_cannibalization": inputs.cannibalization_count,
                },
                confidence=0.9,
                source_engine="cannibalization",
            )
        )
    elif inputs.cannibalization_count > 0:
        score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.MEDIUM)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.CANNIBALIZATION,
                title=f"Address {inputs.cannibalization_count} cannibalization issues",
                description=(
                    f"{inputs.cannibalization_count} keywords show cannibalization. "
                    f"Review content consolidation and canonical tag implementation."
                ),
                impact=OptimizationImpact.MEDIUM,
                effort=OptimizationEffort.MEDIUM,
                priority_score=score,
                affected_keywords=inputs.cannibalized_keywords,
                supporting_metrics={"count": inputs.cannibalization_count},
                confidence=0.85,
                source_engine="cannibalization",
            )
        )

    return recs


def _volatility_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build volatility-related recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.volatile_keyword_count > 0:
        pct = (
            inputs.volatile_keyword_count / inputs.total_volatility_keywords
            if inputs.total_volatility_keywords > 0
            else 0.0
        )
        impact = OptimizationImpact.HIGH if pct > 0.3 else OptimizationImpact.MEDIUM
        score = calculate_priority_score(impact, OptimizationEffort.MEDIUM)

        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.VISIBILITY,
                title=f"Investigate {inputs.volatile_keyword_count} volatile rankings",
                description=(
                    f"{inputs.volatile_keyword_count} keywords show high ranking "
                    f"volatility. Review content stability, competitor activity, "
                    f"and algorithm update impacts."
                ),
                impact=impact,
                effort=OptimizationEffort.MEDIUM,
                priority_score=score,
                affected_keywords=inputs.volatile_keywords,
                supporting_metrics={
                    "volatile_count": inputs.volatile_keyword_count,
                    "total_keywords": inputs.total_volatility_keywords,
                },
                confidence=0.8,
                source_engine="volatility",
            )
        )

    return recs


def _serp_feature_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build SERP feature recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.featured_snippet_occurrences > 0:
        unowned = inputs.featured_snippet_occurrences - inputs.featured_snippet_owned
        if unowned > 0:
            score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.LOW)
            recs.append(
                OptimizationRecommendation(
                    category=OptimizationCategory.SERP_FEATURE,
                    title=f"Capture {unowned} featured snippet opportunities",
                    description=(
                        f"{unowned} featured snippets appear for tracked keywords "
                        f"but target does not own them. Optimise content structure "
                        f"(lists, tables, concise answers) for snippet capture."
                    ),
                    impact=OptimizationImpact.MEDIUM,
                    effort=OptimizationEffort.LOW,
                    priority_score=score,
                    supporting_metrics={
                        "total": inputs.featured_snippet_occurrences,
                        "owned": inputs.featured_snippet_owned,
                        "unowned": unowned,
                    },
                    confidence=0.7,
                    source_engine="serp_features",
                )
            )

    if inputs.people_also_ask_occurrences > 0:
        unowned_paa = inputs.people_also_ask_occurrences - inputs.people_also_ask_owned
        if unowned_paa > 0:
            score = calculate_priority_score(OptimizationImpact.LOW, OptimizationEffort.LOW)
            recs.append(
                OptimizationRecommendation(
                    category=OptimizationCategory.SERP_FEATURE,
                    title=f"Address {unowned_paa} People Also Ask opportunities",
                    description=(
                        f"{unowned_paa} PAA boxes appear but target does not "
                        f"own them. Create FAQ content optimised for PAA inclusion."
                    ),
                    impact=OptimizationImpact.LOW,
                    effort=OptimizationEffort.LOW,
                    priority_score=score,
                    supporting_metrics={
                        "total_paa": inputs.people_also_ask_occurrences,
                        "owned": inputs.people_also_ask_owned,
                    },
                    confidence=0.6,
                    source_engine="serp_features",
                )
            )

    return recs


def _opportunity_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build search opportunity recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.competitor_gap_count > 0:
        score = calculate_priority_score(OptimizationImpact.HIGH, OptimizationEffort.MEDIUM)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.COMPETITOR,
                title=f"Close {inputs.competitor_gap_count} competitor ranking gaps",
                description=(
                    f"Competitors rank for {inputs.competitor_gap_count} keywords "
                    f"where target does not. Create or improve content targeting "
                    f"these keywords."
                ),
                impact=OptimizationImpact.HIGH,
                effort=OptimizationEffort.MEDIUM,
                priority_score=score,
                affected_keywords=inputs.competitor_gap_keywords,
                supporting_metrics={"gap_count": inputs.competitor_gap_count},
                confidence=0.85,
                source_engine="opportunity",
            )
        )

    if inputs.weak_ranking_count > 0:
        score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.LOW)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.KEYWORD,
                title=f"Improve {inputs.weak_ranking_count} weak rankings",
                description=(
                    f"{inputs.weak_ranking_count} keywords rank but could be "
                    f"improved. Enhance content depth, add internal links, "
                    f"and improve page experience."
                ),
                impact=OptimizationImpact.MEDIUM,
                effort=OptimizationEffort.LOW,
                priority_score=score,
                affected_keywords=inputs.weak_ranking_keywords,
                supporting_metrics={"count": inputs.weak_ranking_count},
                confidence=0.75,
                source_engine="opportunity",
            )
        )

    if inputs.content_gap_count > 0:
        score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.HIGH)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.CONTENT,
                title=f"Fill {inputs.content_gap_count} content gaps",
                description=(
                    f"No content exists for {inputs.content_gap_count} keywords "
                    f"but competitors rank. Create new, comprehensive content."
                ),
                impact=OptimizationImpact.MEDIUM,
                effort=OptimizationEffort.HIGH,
                priority_score=score,
                affected_keywords=inputs.content_gap_keywords,
                supporting_metrics={"gap_count": inputs.content_gap_count},
                confidence=0.7,
                source_engine="opportunity",
            )
        )

    return recs


def _aio_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build AI Overview recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.aio_total_keywords > 0:
        aio_pct = inputs.aio_keywords_with_overview / inputs.aio_total_keywords
        citation_rate = (
            inputs.aio_target_cited_count / inputs.aio_keywords_with_overview
            if inputs.aio_keywords_with_overview > 0
            else 0.0
        )

        if aio_pct > 0.3 and citation_rate < 0.3:
            score = calculate_priority_score(OptimizationImpact.HIGH, OptimizationEffort.MEDIUM)
            recs.append(
                OptimizationRecommendation(
                    category=OptimizationCategory.AIO,
                    title="Improve AI Overview citation rate",
                    description=(
                        f"AI Overviews appear for {inputs.aio_keywords_with_overview} "
                        f"keywords but target is cited in only "
                        f"{inputs.aio_target_cited_count}. Create authoritative, "
                        f"structured content optimised for AI citation."
                    ),
                    impact=OptimizationImpact.HIGH,
                    effort=OptimizationEffort.MEDIUM,
                    priority_score=score,
                    supporting_metrics={
                        "aio_keywords": inputs.aio_keywords_with_overview,
                        "target_cited": inputs.aio_target_cited_count,
                        "citation_rate": round(citation_rate, 4),
                    },
                    confidence=0.75,
                    source_engine="aio",
                )
            )

    return recs


def _geo_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build GEO recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.geo_total_keywords > 0 and inputs.geo_overall_mention_rate < 0.2:
        score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.MEDIUM)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.GEO,
                title="Improve generative engine visibility",
                description=(
                    f"Target brand is mentioned in only "
                    f"{inputs.geo_keywords_mentioned} of "
                    f"{inputs.geo_total_keywords} generative engine queries "
                    f"({inputs.geo_overall_mention_rate:.0%}). Build brand "
                    f"authority through comprehensive, well-structured content."
                ),
                impact=OptimizationImpact.MEDIUM,
                effort=OptimizationEffort.MEDIUM,
                priority_score=score,
                supporting_metrics={
                    "mentioned": inputs.geo_keywords_mentioned,
                    "total": inputs.geo_total_keywords,
                    "mention_rate": inputs.geo_overall_mention_rate,
                },
                confidence=0.7,
                source_engine="geo",
            )
        )

    return recs


def _performance_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build performance-related recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.performance_total_pages > 0:
        if inputs.avg_performance_score < 0.5:
            score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.HIGH)
            recs.append(
                OptimizationRecommendation(
                    category=OptimizationCategory.PERFORMANCE,
                    title="Improve page performance metrics",
                    description=(
                        f"Average performance score is "
                        f"{inputs.avg_performance_score:.2f} across "
                        f"{inputs.performance_total_pages} pages. Reduce HTML "
                        f"size, improve content efficiency, and optimise "
                        f"resource loading."
                    ),
                    impact=OptimizationImpact.MEDIUM,
                    effort=OptimizationEffort.HIGH,
                    priority_score=score,
                    supporting_metrics={
                        "avg_score": inputs.avg_performance_score,
                        "pages_below": inputs.pages_below_threshold,
                        "total": inputs.performance_total_pages,
                    },
                    confidence=0.8,
                    source_engine="performance",
                )
            )
        elif inputs.pages_below_threshold > 0:
            score = calculate_priority_score(OptimizationImpact.LOW, OptimizationEffort.MEDIUM)
            recs.append(
                OptimizationRecommendation(
                    category=OptimizationCategory.PERFORMANCE,
                    title=f"Optimise {inputs.pages_below_threshold} underperforming pages",
                    description=(
                        f"{inputs.pages_below_threshold} pages score below 0.4 "
                        f"performance threshold. Review HTML bloat and content "
                        f"efficiency on these pages."
                    ),
                    impact=OptimizationImpact.LOW,
                    effort=OptimizationEffort.MEDIUM,
                    priority_score=score,
                    supporting_metrics={
                        "pages_below": inputs.pages_below_threshold,
                        "avg_score": inputs.avg_performance_score,
                    },
                    confidence=0.75,
                    source_engine="performance",
                )
            )

    return recs


def _entity_recommendations(
    inputs: _IntelligenceInputs,
) -> list[OptimizationRecommendation]:
    """Build entity-related recommendations."""
    recs: list[OptimizationRecommendation] = []

    if inputs.entity_gap_count > 0:
        score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.MEDIUM)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.ENTITY,
                title=f"Address {inputs.entity_gap_count} entity coverage gaps",
                description=(
                    f"{inputs.entity_gap_count} entities appear in competitor "
                    f"content but not in target content. Create content "
                    f"covering these entities to improve topical authority."
                ),
                impact=OptimizationImpact.MEDIUM,
                effort=OptimizationEffort.MEDIUM,
                priority_score=score,
                supporting_metrics={
                    "gap_count": inputs.entity_gap_count,
                    "coverage": inputs.entity_coverage,
                },
                confidence=0.7,
                source_engine="entity",
            )
        )

    if inputs.entity_coverage > 0 and inputs.entity_coverage < 0.3:
        score = calculate_priority_score(OptimizationImpact.MEDIUM, OptimizationEffort.HIGH)
        recs.append(
            OptimizationRecommendation(
                category=OptimizationCategory.ENTITY,
                title="Improve entity coverage ratio",
                description=(
                    f"Entity coverage is {inputs.entity_coverage:.0%}, meaning "
                    f"target content covers few detected entities. Expand "
                    f"content to include key entities in the topic space."
                ),
                impact=OptimizationImpact.MEDIUM,
                effort=OptimizationEffort.HIGH,
                priority_score=score,
                supporting_metrics={"coverage": inputs.entity_coverage},
                confidence=0.65,
                source_engine="entity",
            )
        )

    return recs


def _build_summary(inputs: _IntelligenceInputs, total_recs: int) -> str:
    """Build deterministic executive summary."""
    parts: list[str] = []

    if total_recs == 0:
        return "No optimization recommendations at this time."

    parts.append(
        f"Analysis identified {total_recs} optimisation recommendations "
        f"across {inputs.total_keywords} tracked keywords."
    )

    if inputs.visibility_score < 0.3 and inputs.total_keywords > 0:
        parts.append(
            f"Visibility score ({inputs.visibility_score:.2f}) indicates "
            f"significant room for improvement."
        )

    critical_count = 0
    if inputs.extreme_cannibalization_count > 0:
        critical_count += 1
    if (
        inputs.keywords_not_ranking > inputs.total_keywords * 0.5
        if inputs.total_keywords
        else False
    ):
        critical_count += 1

    if critical_count > 0:
        parts.append(f"{critical_count} critical issue(s) require immediate attention.")

    return " ".join(parts)
