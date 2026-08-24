"""Evidence package builder — aggregates engine outputs into bounded evidence.

This is a pure-function module with zero I/O.  It takes outputs from the
existing engines (Technical SEO, Link Graph, Content Intelligence, Diagnosis)
and produces a structured, bounded :class:`EvidencePackage` suitable for
sending to an LLM.

All data comes from actual engine outputs.  Nothing is fabricated.
"""

from __future__ import annotations

import statistics
from collections import Counter

from sie.domain.models.audit import SiteArchitectureReport, TechnicalAuditResult
from sie.domain.models.content import ContentComparison, ContentMetrics
from sie.domain.models.diagnosis import DiagnosisResult
from sie.domain.models.intelligence import (
    ArchitectureEvidence,
    ContentEvidence,
    CrawlEvidence,
    EvidencePackage,
    TechnicalEvidence,
)


def build_evidence_package(
    *,
    run_id: str,
    technical: TechnicalAuditResult | None = None,
    architecture: SiteArchitectureReport | None = None,
    content_metrics: list[ContentMetrics] | None = None,
    content_comparisons: list[ContentComparison] | None = None,
    diagnosis: DiagnosisResult | None = None,
    crawled_page_count: int = 0,
    status_distribution: dict[str, int] | None = None,
) -> EvidencePackage:
    """Build a bounded evidence package from engine outputs.

    Every field is derived from actual engine data.  Missing engines produce
    zero-valued defaults — never fabricated data.
    """
    return EvidencePackage(
        run_id=run_id,
        crawl=_build_crawl_evidence(
            crawled_page_count=crawled_page_count,
            status_distribution=status_distribution,
            technical=technical,
        ),
        technical=_build_technical_evidence(technical),
        architecture=_build_architecture_evidence(architecture),
        content=_build_content_evidence(content_metrics, content_comparisons),
        diagnosis_issue_count=diagnosis.total_issues if diagnosis else 0,
        diagnosis_issues_by_priority=dict(diagnosis.issues_by_priority) if diagnosis else {},
        diagnosis_issues_by_category=dict(diagnosis.issues_by_category) if diagnosis else {},
    )


def _build_crawl_evidence(
    *,
    crawled_page_count: int,
    status_distribution: dict[str, int] | None,
    technical: TechnicalAuditResult | None,
) -> CrawlEvidence:
    """Build crawl-level evidence."""
    dist = dict(status_distribution) if status_distribution else {}

    # Build HTTP problems list from technical findings
    http_problems: list[dict[str, object]] = []
    if technical:
        for finding in technical.findings:
            if finding.rule_code in ("DX_BROKEN_PAGE", "DX_REDIRECT_CHAIN", "DX_SLOW_RESPONSE"):
                http_problems.append(
                    {
                        "url": finding.affected_url,
                        "rule": finding.rule_code,
                        "severity": finding.severity.value,
                        "message": finding.explanation[:200],
                    }
                )
    # Also add status-based problems from the status distribution
    for status, count in dist.items():
        if status.startswith(("4", "5")) and count > 0:
            http_problems.append(
                {
                    "status": status,
                    "count": count,
                    "message": f"{count} page(s) returned HTTP {status}",
                }
            )

    return CrawlEvidence(
        total_pages=crawled_page_count,
        status_distribution=dist,
        http_problems=tuple(http_problems[:20]),
    )


def _build_technical_evidence(
    technical: TechnicalAuditResult | None,
) -> TechnicalEvidence:
    """Build technical SEO evidence from the audit result."""
    if technical is None:
        return TechnicalEvidence()

    issues_by_rule = dict(technical.summary_by_rule)

    # Count specific issue types from findings
    title_missing = 0
    title_dup = 0
    meta_desc_missing = 0
    canonical_missing = 0
    canonical_mismatch = 0
    h1_missing = 0
    h1_dup = 0
    noindex = 0
    mixed_content = 0
    large_html = 0
    structured_data_missing = 0
    hreflang_issues = 0

    for finding in technical.findings:
        code = finding.rule_code
        if "TITLE" in code and "MISSING" in code:
            title_missing += 1
        elif "TITLE" in code and "DUPLICATE" in code:
            title_dup += 1
        elif "META_DESC" in code and "MISSING" in code:
            meta_desc_missing += 1
        elif "CANONICAL" in code and "MISSING" in code:
            canonical_missing += 1
        elif "CANONICAL" in code and ("MISMATCH" in code or "REDIRECT" in code):
            canonical_mismatch += 1
        elif "H1" in code and "MISSING" in code:
            h1_missing += 1
        elif "H1" in code and "DUPLICATE" in code:
            h1_dup += 1
        elif "NOINDEX" in code:
            noindex += 1
        elif "MIXED_CONTENT" in code:
            mixed_content += 1
        elif "LARGE_HTML" in code:
            large_html += 1
        elif "STRUCTURED_DATA" in code and "MISSING" in code:
            structured_data_missing += 1
        elif "HREFLANG" in code:
            hreflang_issues += 1

    return TechnicalEvidence(
        title_missing_count=title_missing,
        title_duplicate_count=title_dup,
        meta_desc_missing_count=meta_desc_missing,
        canonical_missing_count=canonical_missing,
        canonical_mismatch_count=canonical_mismatch,
        h1_missing_count=h1_missing,
        h1_duplicate_count=h1_dup,
        robots_noindex_count=noindex,
        mixed_content_count=mixed_content,
        large_html_count=large_html,
        structured_data_missing_count=structured_data_missing,
        hreflang_issues_count=hreflang_issues,
        issues_by_rule=issues_by_rule,
    )


def _build_architecture_evidence(
    architecture: SiteArchitectureReport | None,
) -> ArchitectureEvidence:
    """Build architecture evidence from the link graph report."""
    if architecture is None:
        return ArchitectureEvidence()

    return ArchitectureEvidence(
        total_internal_links=architecture.total_internal_links,
        avg_links_per_page=architecture.avg_links_per_page,
        orphan_count=len(architecture.orphans),
        orphan_urls=tuple(architecture.orphans[:15]),
        dead_end_count=len(architecture.dead_ends),
        dead_end_urls=tuple(architecture.dead_ends[:15]),
        max_depth=architecture.max_depth,
        avg_depth=architecture.avg_depth,
        thin_connection_count=len(architecture.thin_connection_pages),
        pagerank_top_5=tuple(architecture.pagerank_top_10[:5]),
        pagerank_bottom_5=tuple(architecture.pagerank_bottom_10[:5]),
    )


def _build_content_evidence(
    content_metrics: list[ContentMetrics] | None,
    content_comparisons: list[ContentComparison] | None,
) -> ContentEvidence:
    """Build content evidence from content intelligence outputs."""
    if not content_metrics:
        return ContentEvidence()

    word_counts = [m.word_count for m in content_metrics]
    quality_scores = [m.quality_score for m in content_metrics]
    readability_scores = [m.readability.flesch_reading_ease for m in content_metrics]

    thin_urls = [m.url for m in content_metrics if m.thin_content]
    total_images = sum(m.images.total_images for m in content_metrics)
    images_without_alt = sum(m.images.images_without_alt for m in content_metrics)

    # Quality distribution
    quality_dist: dict[str, int] = Counter()
    for m in content_metrics:
        quality_dist[m.quality_tier.value] += 1

    # Top keywords (aggregate across pages)
    keyword_counter: Counter[str] = Counter()
    for m in content_metrics:
        for word, count, _density in m.keywords.top_keywords:
            keyword_counter[word] += count
    top_keywords = [
        {"keyword": word, "count": count}
        for word, count in keyword_counter.most_common(10)
    ]

    # Keyword stuffing detection
    stuffing_count = sum(
        1 for m in content_metrics if m.keywords.keyword_stuffing_score > 0.05
    )

    # Duplicate pairs
    dup_pairs: list[dict[str, str]] = []
    if content_comparisons:
        for c in content_comparisons:
            if c.duplicate_status.value in ("near_duplicate", "exact_duplicate"):
                dup_pairs.append(
                    {
                        "url_a": c.url_a,
                        "url_b": c.url_b,
                        "similarity": f"{c.similarity_score:.2f}",
                        "status": c.duplicate_status.value,
                    }
                )

    return ContentEvidence(
        avg_word_count=round(statistics.mean(word_counts), 1) if word_counts else 0.0,
        median_word_count=round(statistics.median(word_counts), 1) if word_counts else 0.0,
        thin_content_count=len(thin_urls),
        thin_content_urls=tuple(thin_urls[:15]),
        avg_quality_score=round(statistics.mean(quality_scores), 2) if quality_scores else 0.0,
        quality_distribution=dict(quality_dist),
        duplicate_pair_count=len(dup_pairs),
        duplicate_pairs=tuple(dup_pairs[:10]),
        avg_readability_score=round(
            statistics.mean(readability_scores), 1
        )
        if readability_scores
        else 0.0,
        images_without_alt_count=images_without_alt,
        total_images=total_images,
        top_keywords=tuple(top_keywords[:10]),
        keyword_stuffing_count=stuffing_count,
    )
