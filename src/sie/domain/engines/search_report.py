"""Consolidated Intelligence Reporting engine (Phase 8).

Pure functions that aggregate all intelligence engine outputs into a
single structured report with executive summary, component breakdowns,
and prioritised action items.

This engine does NOT recalculate SEO analytics — it consumes existing
results and generates deterministic, structured reports.
"""

from __future__ import annotations

from sie.domain.models.search_report import (
    ActionItem,
    ActionPriority,
    IntelligenceReport,
    ReportComponent,
    ReportStatus,
)

__all__ = [
    "generate_intelligence_report",
]


def generate_intelligence_report(
    dataset_id: str,
    *,
    # Ranking / analytics
    visibility_score: float = 0.0,
    total_keywords: int = 0,
    keywords_ranking: int = 0,
    keywords_not_ranking: int = 0,
    top_10_count: int = 0,
    serp_feature_count: int = 0,
    # Cannibalization
    cannibalization_count: int = 0,
    extreme_cannibalization_count: int = 0,
    # Volatility
    volatile_keyword_count: int = 0,
    # Opportunities
    total_opportunities: int = 0,
    competitor_gap_count: int = 0,
    weak_ranking_count: int = 0,
    content_gap_count: int = 0,
    # AIO
    aio_keywords_with_overview: int = 0,
    aio_target_cited_count: int = 0,
    aio_total_keywords: int = 0,
    # GEO
    geo_keywords_mentioned: int = 0,
    geo_total_keywords: int = 0,
    # Performance
    avg_performance_score: float = 0.0,
    performance_total_pages: int = 0,
    performance_findings_count: int = 0,
    # Entity
    entity_total_unique: int = 0,
    entity_coverage: float = 0.0,
    entity_gap_count: int = 0,
    # Optimization
    optimization_recommendation_count: int = 0,
    high_priority_optimization_count: int = 0,
    quick_wins_count: int = 0,
    # Industry Intelligence (Phase 11)
    industry_findings_count: int = 0,
    industry_opportunities_count: int = 0,
    # Metadata
    metadata: dict[str, object] | None = None,
) -> IntelligenceReport:
    """Generate a consolidated intelligence report from all engine outputs.

    Aggregates available intelligence components into a single structured
    report with executive summary, per-component breakdowns, and
    prioritised cross-cutting action items.

    Deterministic: same inputs always produce the same output.
    """
    components: list[ReportComponent] = []
    action_items: list[ActionItem] = []
    order_counter = 1

    # ── Ranking Component ──
    if total_keywords > 0:
        ranking_summary = _ranking_summary(
            visibility_score, keywords_ranking, keywords_not_ranking, top_10_count
        )
        components.append(
            ReportComponent(
                name="ranking",
                status=ReportStatus.COMPLETE,
                summary=ranking_summary,
                key_metrics={
                    "visibility_score": visibility_score,
                    "total_keywords": total_keywords,
                    "keywords_ranking": keywords_ranking,
                    "top_10_count": top_10_count,
                },
                finding_count=1 if keywords_not_ranking > 0 else 0,
            )
        )

        if keywords_not_ranking > 0:
            action_items.append(
                ActionItem(
                    order=order_counter,
                    priority=ActionPriority.HIGH,
                    title=f"Address {keywords_not_ranking} non-ranking keywords",
                    description=(
                        f"{keywords_not_ranking} of {total_keywords} keywords have no ranking."
                    ),
                    source_components=("ranking",),
                    affected_keywords=(),
                    effort="high",
                    confidence=0.9,
                )
            )
            order_counter += 1

    # ── SERP Features Component ──
    if serp_feature_count > 0:
        components.append(
            ReportComponent(
                name="serp_features",
                status=ReportStatus.COMPLETE,
                summary=f"{serp_feature_count} SERP feature opportunities detected.",
                key_metrics={"serp_feature_count": serp_feature_count},
                finding_count=1,
            )
        )

    # ── Cannibalization Component ──
    if cannibalization_count > 0:
        sev = "extreme" if extreme_cannibalization_count > 0 else "moderate"
        priority = (
            ActionPriority.CRITICAL if extreme_cannibalization_count > 0 else ActionPriority.HIGH
        )
        components.append(
            ReportComponent(
                name="cannibalization",
                status=ReportStatus.COMPLETE,
                summary=(
                    f"{cannibalization_count} cannibalization issues detected ({sev} severity)."
                ),
                key_metrics={
                    "total": cannibalization_count,
                    "extreme": extreme_cannibalization_count,
                },
                finding_count=cannibalization_count,
            )
        )
        action_items.append(
            ActionItem(
                order=order_counter,
                priority=priority,
                title=f"Resolve {cannibalization_count} cannibalization issues",
                description=(f"{cannibalization_count} keywords show URL cannibalization."),
                source_components=("cannibalization",),
                effort="medium",
                confidence=0.9,
            )
        )
        order_counter += 1

    # ── Volatility Component ──
    if volatile_keyword_count > 0:
        components.append(
            ReportComponent(
                name="volatility",
                status=ReportStatus.COMPLETE,
                summary=f"{volatile_keyword_count} keywords with high ranking volatility.",
                key_metrics={"volatile_count": volatile_keyword_count},
                finding_count=volatile_keyword_count,
            )
        )
        action_items.append(
            ActionItem(
                order=order_counter,
                priority=ActionPriority.MEDIUM,
                title=f"Investigate {volatile_keyword_count} volatile rankings",
                description="High ranking volatility detected on multiple keywords.",
                source_components=("volatility",),
                effort="medium",
                confidence=0.8,
            )
        )
        order_counter += 1

    # ── Opportunities Component ──
    if total_opportunities > 0:
        opp_findings = competitor_gap_count + weak_ranking_count + content_gap_count
        components.append(
            ReportComponent(
                name="opportunities",
                status=ReportStatus.COMPLETE,
                summary=(
                    f"{total_opportunities} search opportunities identified: "
                    f"{competitor_gap_count} competitor gaps, "
                    f"{weak_ranking_count} weak rankings, "
                    f"{content_gap_count} content gaps."
                ),
                key_metrics={
                    "total": total_opportunities,
                    "competitor_gaps": competitor_gap_count,
                    "weak_rankings": weak_ranking_count,
                    "content_gaps": content_gap_count,
                },
                finding_count=opp_findings,
                recommendation_count=total_opportunities,
            )
        )
        if competitor_gap_count > 0:
            action_items.append(
                ActionItem(
                    order=order_counter,
                    priority=ActionPriority.HIGH,
                    title=f"Close {competitor_gap_count} competitor ranking gaps",
                    description="Competitors rank for keywords where target does not.",
                    source_components=("opportunities",),
                    effort="medium",
                    confidence=0.85,
                )
            )
            order_counter += 1

    # ── AIO Component ──
    if aio_total_keywords > 0:
        citation_rate = (
            aio_target_cited_count / aio_keywords_with_overview
            if aio_keywords_with_overview > 0
            else 0.0
        )
        components.append(
            ReportComponent(
                name="aio",
                status=ReportStatus.COMPLETE,
                summary=(
                    f"AI Overviews present for {aio_keywords_with_overview} "
                    f"of {aio_total_keywords} keywords. "
                    f"Target cited in {aio_target_cited_count} "
                    f"({citation_rate:.0%})."
                ),
                key_metrics={
                    "keywords_with_overview": aio_keywords_with_overview,
                    "target_cited": aio_target_cited_count,
                    "total": aio_total_keywords,
                    "citation_rate": round(citation_rate, 4),
                },
                finding_count=1 if citation_rate < 0.3 and aio_keywords_with_overview > 0 else 0,
            )
        )

    # ── GEO Component ──
    if geo_total_keywords > 0:
        mention_rate = (
            geo_keywords_mentioned / geo_total_keywords if geo_total_keywords > 0 else 0.0
        )
        components.append(
            ReportComponent(
                name="geo",
                status=ReportStatus.COMPLETE,
                summary=(
                    f"Target mentioned in {geo_keywords_mentioned} of "
                    f"{geo_total_keywords} generative queries "
                    f"({mention_rate:.0%})."
                ),
                key_metrics={
                    "mentioned": geo_keywords_mentioned,
                    "total": geo_total_keywords,
                    "mention_rate": round(mention_rate, 4),
                },
                finding_count=1 if mention_rate < 0.2 else 0,
            )
        )

    # ── Performance Component ──
    if performance_total_pages > 0:
        components.append(
            ReportComponent(
                name="performance",
                status=ReportStatus.COMPLETE,
                summary=(
                    f"Average performance score: {avg_performance_score:.2f} "
                    f"across {performance_total_pages} pages."
                ),
                key_metrics={
                    "avg_score": avg_performance_score,
                    "total_pages": performance_total_pages,
                    "findings": performance_findings_count,
                },
                finding_count=performance_findings_count,
            )
        )

    # ── Entity Component ──
    if entity_total_unique > 0:
        components.append(
            ReportComponent(
                name="entity",
                status=ReportStatus.COMPLETE,
                summary=(
                    f"{entity_total_unique} unique entities detected. "
                    f"Coverage: {entity_coverage:.0%}. "
                    f"{entity_gap_count} gaps identified."
                ),
                key_metrics={
                    "total_entities": entity_total_unique,
                    "coverage": entity_coverage,
                    "gaps": entity_gap_count,
                },
                finding_count=entity_gap_count,
            )
        )

    # ── Industry Intelligence Component (Phase 11) ──
    if industry_findings_count > 0 or industry_opportunities_count > 0:
        components.append(
            ReportComponent(
                name="industry",
                status=ReportStatus.COMPLETE,
                summary=(
                    f"Industry intelligence identified {industry_findings_count} findings "
                    f"and {industry_opportunities_count} opportunities."
                ),
                key_metrics={
                    "findings": industry_findings_count,
                    "opportunities": industry_opportunities_count,
                },
                finding_count=industry_findings_count,
                recommendation_count=industry_opportunities_count,
            )
        )

        if industry_findings_count > 0:
            action_items.append(
                ActionItem(
                    order=order_counter,
                    priority=ActionPriority.HIGH,
                    title=f"Address {industry_findings_count} industry-specific findings",
                    description=(
                        "Industry-specific analysis has identified opportunities "
                        "for content expansion and optimization."
                    ),
                    source_components=("industry",),
                    effort="medium",
                    confidence=0.85,
                )
            )
            order_counter += 1

    # ── Optimization Component ──
    if optimization_recommendation_count > 0:
        components.append(
            ReportComponent(
                name="optimization",
                status=ReportStatus.COMPLETE,
                summary=(
                    f"{optimization_recommendation_count} optimization "
                    f"recommendations ({high_priority_optimization_count} high "
                    f"priority, {quick_wins_count} quick wins)."
                ),
                key_metrics={
                    "total": optimization_recommendation_count,
                    "high_priority": high_priority_optimization_count,
                    "quick_wins": quick_wins_count,
                },
                finding_count=optimization_recommendation_count,
                recommendation_count=optimization_recommendation_count,
            )
        )

    # ── Build executive summary ──
    summary = _build_executive_summary(
        components,
        total_keywords,
        visibility_score,
        cannibalization_count,
        volatile_keyword_count,
        total_opportunities,
    )

    # ── Aggregate counts ──
    total_findings = sum(c.finding_count for c in components)
    total_recs = sum(c.recommendation_count for c in components)

    return IntelligenceReport(
        dataset_id=dataset_id,
        summary=summary,
        components=tuple(components),
        action_items=tuple(action_items),
        total_findings=total_findings,
        total_recommendations=total_recs,
        metadata=metadata or {},
    )


def _ranking_summary(
    visibility_score: float,
    keywords_ranking: int,
    keywords_not_ranking: int,
    top_10_count: int,
) -> str:
    """Build ranking component summary."""
    parts = []
    parts.append(
        f"Visibility score: {visibility_score:.2f}. "
        f"{keywords_ranking} keywords ranking, "
        f"{keywords_not_ranking} not ranking."
    )
    if top_10_count > 0:
        parts.append(f"{top_10_count} keywords in top 10.")
    return " ".join(parts)


def _build_executive_summary(
    components: list[ReportComponent],
    total_keywords: int,
    visibility_score: float,
    cannibalization_count: int,
    volatile_keyword_count: int,
    total_opportunities: int,
) -> str:
    """Build deterministic executive summary."""
    parts: list[str] = []

    active_components = [c for c in components if c.status == ReportStatus.COMPLETE]

    parts.append(
        f"Intelligence report covers {total_keywords} tracked keywords "
        f"across {len(active_components)} analysis components."
    )

    if visibility_score > 0:
        if visibility_score >= 0.7:
            parts.append(f"Visibility score ({visibility_score:.2f}) is strong.")
        elif visibility_score >= 0.3:
            parts.append(f"Visibility score ({visibility_score:.2f}) has room for improvement.")
        else:
            parts.append(
                f"Visibility score ({visibility_score:.2f}) indicates "
                f"significant optimisation needed."
            )

    critical_issues = 0
    if cannibalization_count > 5:
        critical_issues += 1
    if volatile_keyword_count > total_keywords * 0.3 if total_keywords else False:
        critical_issues += 1

    if critical_issues > 0:
        parts.append(f"{critical_issues} critical issue(s) require immediate attention.")
    elif total_opportunities > 0:
        parts.append(
            f"{total_opportunities} optimisation opportunities identified for prioritised action."
        )
    else:
        parts.append("No critical issues detected.")

    return " ".join(parts)
