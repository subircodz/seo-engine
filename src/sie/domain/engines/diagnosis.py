"""SEO Diagnosis engine — deterministic cross-engine analysis.

Combines signals from Technical SEO, Link Graph, and Content Intelligence
engines to identify structured SEO problems with evidence, priorities,
and recommendations.

All rules are deterministic (no LLM).  Language uses measured phrasing:
"potential ranking issue", "SEO risk", "optimization opportunity",
"technical obstacle".
"""

from __future__ import annotations

from collections import Counter

from sie.domain.models.audit import (
    AuditFinding,
    SiteArchitectureReport,
    TechnicalAuditResult,
)
from sie.domain.models.content import ContentMetrics
from sie.domain.models.diagnosis import (
    DiagnosisCategory,
    DiagnosisEvidence,
    DiagnosisIssue,
    DiagnosisPriority,
    DiagnosisResult,
    DiagnosisSeverity,
)

# ════════════════════════════════════════════════════════════════════════════
# Diagnosis rule protocol
# ════════════════════════════════════════════════════════════════════════════


class DiagnosisRule:
    """Base class for deterministic diagnosis rules."""

    code: str
    category: DiagnosisCategory
    severity: DiagnosisSeverity
    priority: DiagnosisPriority
    source_engine: str

    def evaluate(
        self,
        technical: TechnicalAuditResult | None,
        architecture: SiteArchitectureReport | None,
        content_metrics: list[ContentMetrics] | None,
    ) -> tuple[DiagnosisIssue, ...]:
        raise NotImplementedError


# ════════════════════════════════════════════════════════════════════════════
# Helper: aggregate technical findings by page + rule
# ════════════════════════════════════════════════════════════════════════════


def _findings_by_code(
    technical: TechnicalAuditResult | None,
) -> dict[str, list[AuditFinding]]:
    if technical is None:
        return {}
    by_code: dict[str, list[AuditFinding]] = {}
    for f in technical.findings:
        by_code.setdefault(f.rule_code, []).append(f)
    return by_code


def _content_by_url(
    content_metrics: list[ContentMetrics] | None,
) -> dict[str, ContentMetrics]:
    if content_metrics is None:
        return {}
    return {m.url: m for m in content_metrics}


# ════════════════════════════════════════════════════════════════════════════
# P0 — Critical issues
# ════════════════════════════════════════════════════════════════════════════


class MissingTitleDiagnosis(DiagnosisRule):
    """Detect pages with no title tag."""

    code = "DX_TITLE_MISSING"
    category = DiagnosisCategory.META
    severity = DiagnosisSeverity.CRITICAL
    priority = DiagnosisPriority.P0
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("TITLE_MISSING", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Page is missing a <title> tag. "
                    "Title tags are a primary on-page signal and a "
                    "potential ranking issue.",
                    recommendation="Add a unique, descriptive title "
                    "(30-60 characters) to this page.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="title_present",
                            metric_value=False,
                            description="No <title> element found",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class DuplicateTitleDiagnosis(DiagnosisRule):
    """Detect pages sharing the same title."""

    code = "DX_TITLE_DUPLICATE"
    category = DiagnosisCategory.META
    severity = DiagnosisSeverity.CRITICAL
    priority = DiagnosisPriority.P0
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("TITLE_DUPLICATE", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Title tags are shared across multiple pages. "
                    "Duplicate titles make it harder for search engines to "
                    "distinguish page relevance.",
                    recommendation="Write a unique, descriptive title for each page.",
                    evidence=[
                        DiagnosisEvidence(
                            metric_name="duplicate_title_count",
                            metric_value=len(f.affected_elements),
                            description="Other pages sharing this title",
                        ),
                        *(
                            DiagnosisEvidence(
                                metric_name="duplicate_page",
                                source_url=u,
                                description="Page with identical title",
                            )
                            for u in f.affected_elements[:5]
                        ),
                    ],
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class MissingMetaDescriptionDiagnosis(DiagnosisRule):
    """Detect pages with no meta description."""

    code = "DX_META_DESC_MISSING"
    category = DiagnosisCategory.META
    severity = DiagnosisSeverity.CRITICAL
    priority = DiagnosisPriority.P0
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("META_DESC_MISSING", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Page is missing a meta description. "
                    "While not a direct ranking factor, meta descriptions "
                    "influence click-through rate from search results.",
                    recommendation="Add a meta description (120-160 characters) "
                    "that accurately describes the page content.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="meta_description_present",
                            metric_value=False,
                            description="No meta description found",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class MissingCanonicalDiagnosis(DiagnosisRule):
    """Detect pages with no canonical tag."""

    code = "DX_CANONICAL_MISSING"
    category = DiagnosisCategory.META
    severity = DiagnosisSeverity.CRITICAL
    priority = DiagnosisPriority.P0
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("CANONICAL_MISSING", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Page is missing a canonical tag. "
                    "Without canonicalization, search engines may index "
                    "duplicate versions of this page, diluting ranking signals.",
                    recommendation="Add a self-referencing canonical tag to "
                    "indicate the preferred URL.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="canonical_present",
                            metric_value=False,
                            description="No canonical link element found",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class BrokenPageDiagnosis(DiagnosisRule):
    """Detect pages returning 4xx/5xx status codes."""

    code = "DX_BROKEN_PAGE"
    category = DiagnosisCategory.STATUS
    severity = DiagnosisSeverity.CRITICAL
    priority = DiagnosisPriority.P0
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for code_filter in ("STATUS_404", "STATUS_5XX"):
            for f in by_code.get(code_filter, []):
                issues.append(
                    DiagnosisIssue(
                        rule_code=self.code,
                        category=self.category,
                        severity=self.severity,
                        priority=self.priority,
                        affected_url=f.page_url,
                        explanation=f"{f.message}. "
                        "Broken pages are a technical obstacle that prevents "
                        "crawling and indexing.",
                        recommendation="Fix the URL, restore the content, or "
                        "redirect to a valid page.",
                        evidence=(
                            DiagnosisEvidence(
                                metric_name="status_code",
                                metric_value=f.page_url,
                                description=f.message,
                            ),
                        ),
                        source_engine=self.source_engine,
                    )
                )
        return tuple(issues)


class NoindexDiagnosis(DiagnosisRule):
    """Detect pages marked noindex that may be unintentional."""

    code = "DX_NOINDEX"
    category = DiagnosisCategory.META
    severity = DiagnosisSeverity.HIGH
    priority = DiagnosisPriority.P1
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("META_ROBOTS_NOINDEX", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Page is marked noindex. If this is "
                    "unintentional, the page will be excluded from search "
                    "engine indices.",
                    recommendation="Verify this page should be noindex. "
                    "Remove the noindex directive if the page should appear "
                    "in search results.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="meta_robots",
                            metric_value="noindex",
                            description="noindex directive detected",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class MissingH1Diagnosis(DiagnosisRule):
    """Detect pages with no H1 tag."""

    code = "DX_H1_MISSING"
    category = DiagnosisCategory.STRUCTURE
    severity = DiagnosisSeverity.CRITICAL
    priority = DiagnosisPriority.P0
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("H1_MISSING", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Page has no H1 heading. H1 tags signal the "
                    "main topic to both users and search engines.",
                    recommendation="Add exactly one H1 tag that describes the "
                    "page's primary topic.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="h1_count",
                            metric_value=0,
                            threshold=1,
                            description="No H1 element found",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class MultipleH1Diagnosis(DiagnosisRule):
    """Detect pages with more than one H1 tag."""

    code = "DX_H1_MULTIPLE"
    category = DiagnosisCategory.STRUCTURE
    severity = DiagnosisSeverity.CRITICAL
    priority = DiagnosisPriority.P0
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("H1_MULTIPLE", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Page has multiple H1 tags. "
                    "Multiple H1s can confuse search engines about the "
                    "page's primary topic.",
                    recommendation="Use exactly one H1 tag per page.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="h1_count",
                            metric_value=(
                                f.affected_elements[0] if f.affected_elements else "multiple"
                            ),
                            threshold=1,
                            description="More than one H1 element found",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class MixedContentDiagnosis(DiagnosisRule):
    """Detect HTTPS pages loading HTTP resources."""

    code = "DX_MIXED_CONTENT"
    category = DiagnosisCategory.SECURITY
    severity = DiagnosisSeverity.HIGH
    priority = DiagnosisPriority.P1
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("MIXED_CONTENT", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Page loads resources over HTTP while served "
                    "over HTTPS. This is a security risk and may trigger "
                    "browser warnings.",
                    recommendation="Update all resource URLs to use HTTPS.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="mixed_content",
                            metric_value=True,
                            description="HTTP resources found on HTTPS page",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class MissingStructuredDataDiagnosis(DiagnosisRule):
    """Detect pages without structured data (JSON-LD)."""

    code = "DX_STRUCTURED_DATA_MISSING"
    category = DiagnosisCategory.STRUCTURED_DATA
    severity = DiagnosisSeverity.MEDIUM
    priority = DiagnosisPriority.P2
    source_engine = "technical_seo"

    def evaluate(self, technical, architecture, content_metrics):
        by_code = _findings_by_code(technical)
        issues: list[DiagnosisIssue] = []
        for f in by_code.get("JSONLD_MISSING", []):
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=f.page_url,
                    explanation="Page has no JSON-LD structured data. "
                    "Structured data is an optimization opportunity that "
                    "can enable rich results in search listings.",
                    recommendation="Add relevant Schema.org structured data "
                    "via JSON-LD for this page's content type.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="jsonld_present",
                            metric_value=False,
                            description="No application/ld+json blocks found",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class PoorImageAltCoverageDiagnosis(DiagnosisRule):
    """Detect pages with high percentage of images missing alt text."""

    code = "DX_IMAGE_ALT_COVERAGE"
    category = DiagnosisCategory.ACCESSIBILITY
    severity = DiagnosisSeverity.MEDIUM
    priority = DiagnosisPriority.P2
    source_engine = "content_intelligence"
    _THRESHOLD = 50.0  # percent

    def evaluate(self, technical, architecture, content_metrics):
        by_url = _content_by_url(content_metrics)
        issues: list[DiagnosisIssue] = []
        for url, m in by_url.items():
            if m.images.total_images > 0 and m.images.missing_alt_percentage > self._THRESHOLD:
                issues.append(
                    DiagnosisIssue(
                        rule_code=self.code,
                        category=self.category,
                        severity=self.severity,
                        priority=self.priority,
                        affected_url=url,
                        explanation=f"{m.images.missing_alt_percentage:.0f}% of images "
                        f"({m.images.images_without_alt}/{m.images.total_images}) "
                        "are missing alt text. This is an accessibility gap and "
                        "an SEO optimization opportunity.",
                        recommendation="Add descriptive alt text to all images, "
                        "especially those conveying content.",
                        evidence=(
                            DiagnosisEvidence(
                                metric_name="images_missing_alt_pct",
                                metric_value=m.images.missing_alt_percentage,
                                threshold=self._THRESHOLD,
                                description=f"{m.images.images_without_alt} of "
                                f"{m.images.total_images} images lack alt text",
                            ),
                        ),
                        source_engine=self.source_engine,
                    )
                )
        return tuple(issues)


# ════════════════════════════════════════════════════════════════════════════
# Architecture-based diagnoses
# ════════════════════════════════════════════════════════════════════════════


class OrphanPageDiagnosis(DiagnosisRule):
    """Detect orphan pages (no internal incoming links)."""

    code = "DX_ORPHAN_PAGE"
    category = DiagnosisCategory.LINKS
    severity = DiagnosisSeverity.HIGH
    priority = DiagnosisPriority.P1
    source_engine = "link_graph"

    def evaluate(self, technical, architecture, content_metrics):
        if architecture is None:
            return ()
        issues: list[DiagnosisIssue] = []
        for url in architecture.orphans:
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=url,
                    explanation="Page has no internal incoming links "
                    "(orphan page). Crawlers may have difficulty discovering "
                    "and prioritizing this page.",
                    recommendation="Add internal links from relevant pages "
                    "to ensure this page is crawlable and receives "
                    "ranking signals.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="incoming_internal_links",
                            metric_value=0,
                            threshold=1,
                            description="No internal pages link to this URL",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class DeadEndPageDiagnosis(DiagnosisRule):
    """Detect dead-end pages (no outgoing internal links)."""

    code = "DX_DEAD_END_PAGE"
    category = DiagnosisCategory.LINKS
    severity = DiagnosisSeverity.MEDIUM
    priority = DiagnosisPriority.P2
    source_engine = "link_graph"

    def evaluate(self, technical, architecture, content_metrics):
        if architecture is None:
            return ()
        issues: list[DiagnosisIssue] = []
        for url in architecture.dead_ends:
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url=url,
                    explanation="Page has no outgoing internal links "
                    "(dead end). This is a crawl-path dead end that may "
                    "prevent crawlers from discovering other pages.",
                    recommendation="Add relevant internal links to guide "
                    "users and crawlers to related content.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="outgoing_internal_links",
                            metric_value=0,
                            threshold=1,
                            description="Page links to no other internal pages",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class ExcessiveCrawlDepthDiagnosis(DiagnosisRule):
    """Detect pages beyond the recommended crawl depth."""

    code = "DX_EXCESSIVE_DEPTH"
    category = DiagnosisCategory.ARCHITECTURE
    severity = DiagnosisSeverity.MEDIUM
    priority = DiagnosisPriority.P2
    source_engine = "link_graph"
    _MAX_DEPTH = 5

    def evaluate(self, technical, architecture, content_metrics):
        if architecture is None:
            return ()
        issues: list[DiagnosisIssue] = []
        if architecture.max_depth > self._MAX_DEPTH:
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url="(site-wide)",
                    explanation=f"Maximum crawl depth is {architecture.max_depth} "
                    f"(recommended: {self._MAX_DEPTH}). Pages beyond this depth "
                    "are harder for crawlers to discover and may receive less "
                    "crawl attention.",
                    recommendation="Flatten site architecture by adding "
                    "shallower paths to important content.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="max_depth",
                            metric_value=architecture.max_depth,
                            threshold=self._MAX_DEPTH,
                            description="Maximum click depth from root",
                        ),
                        DiagnosisEvidence(
                            metric_name="avg_depth",
                            metric_value=architecture.avg_depth,
                            description="Average click depth across all pages",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


class WeakInternalLinkingDiagnosis(DiagnosisRule):
    """Detect site-wide weak internal linking patterns."""

    code = "DX_WEAK_INTERNAL_LINKING"
    category = DiagnosisCategory.LINKS
    severity = DiagnosisSeverity.MEDIUM
    priority = DiagnosisPriority.P2
    source_engine = "link_graph"
    _MIN_AVG_LINKS = 3.0

    def evaluate(self, technical, architecture, content_metrics):
        if architecture is None:
            return ()
        issues: list[DiagnosisIssue] = []
        if architecture.total_pages > 1 and architecture.avg_links_per_page < self._MIN_AVG_LINKS:
            issues.append(
                DiagnosisIssue(
                    rule_code=self.code,
                    category=self.category,
                    severity=self.severity,
                    priority=self.priority,
                    affected_url="(site-wide)",
                    explanation=f"Average internal links per page is "
                    f"{architecture.avg_links_per_page:.1f} (recommended: "
                    f">{self._MIN_AVG_LINKS:.0f}). Weak internal linking "
                    "reduces crawl efficiency and dilutes PageRank flow.",
                    recommendation="Strengthen internal linking by connecting "
                    "related content and creating topical clusters.",
                    evidence=(
                        DiagnosisEvidence(
                            metric_name="avg_links_per_page",
                            metric_value=architecture.avg_links_per_page,
                            threshold=self._MIN_AVG_LINKS,
                            description="Average internal links per page",
                        ),
                        DiagnosisEvidence(
                            metric_name="total_pages",
                            metric_value=architecture.total_pages,
                            description="Total pages in crawl",
                        ),
                    ),
                    source_engine=self.source_engine,
                )
            )
        return tuple(issues)


# ════════════════════════════════════════════════════════════════════════════
# Content-based diagnoses
# ════════════════════════════════════════════════════════════════════════════


class ThinContentDiagnosis(DiagnosisRule):
    """Detect thin content pages based on word count."""

    code = "DX_THIN_CONTENT"
    category = DiagnosisCategory.CONTENT
    severity = DiagnosisSeverity.HIGH
    priority = DiagnosisPriority.P1
    source_engine = "content_intelligence"
    _THRESHOLD = 150

    def evaluate(self, technical, architecture, content_metrics):
        by_url = _content_by_url(content_metrics)
        issues: list[DiagnosisIssue] = []
        for url, m in by_url.items():
            if m.thin_content or m.word_count < self._THRESHOLD:
                issues.append(
                    DiagnosisIssue(
                        rule_code=self.code,
                        category=self.category,
                        severity=self.severity,
                        priority=self.priority,
                        affected_url=url,
                        explanation=f"Page has only {m.word_count} words "
                        f"(threshold: {self._THRESHOLD}). Thin content is "
                        "an SEO risk as it may not provide sufficient value "
                        "to justify ranking.",
                        recommendation="Expand the page with substantive, "
                        "relevant content that addresses user intent.",
                        evidence=(
                            DiagnosisEvidence(
                                metric_name="word_count",
                                metric_value=m.word_count,
                                threshold=self._THRESHOLD,
                                description="Total visible word count",
                            ),
                            DiagnosisEvidence(
                                metric_name="quality_tier",
                                metric_value=m.quality_tier.value,
                                description="Content quality classification",
                            ),
                        ),
                        source_engine=self.source_engine,
                    )
                )
        return tuple(issues)


class DuplicateContentDiagnosis(DiagnosisRule):
    """Detect duplicate/near-duplicate content across pages."""

    code = "DX_DUPLICATE_CONTENT"
    category = DiagnosisCategory.CONTENT
    severity = DiagnosisSeverity.HIGH
    priority = DiagnosisPriority.P1
    source_engine = "content_comparison"

    def evaluate(self, technical, architecture, content_metrics):
        if content_metrics is None:
            return ()
        from sie.domain.engines.content_comparison import find_duplicate_groups

        groups = find_duplicate_groups(content_metrics)
        issues: list[DiagnosisIssue] = []
        for group in groups:
            if len(group) < 2:
                continue
            # Report the second+ pages as duplicates of the first
            for url in group[1:]:
                issues.append(
                    DiagnosisIssue(
                        rule_code=self.code,
                        category=self.category,
                        severity=self.severity,
                        priority=self.priority,
                        affected_url=url,
                        explanation=f"Page is a duplicate of {group[0]}. "
                        "Duplicate content splits ranking signals across "
                        "multiple URLs, which is an SEO risk.",
                        recommendation="Consolidate duplicate pages using "
                        "canonical tags, redirects, or by merging content.",
                        evidence=(
                            DiagnosisEvidence(
                                metric_name="duplicate_group_size",
                                metric_value=len(group),
                                threshold=2,
                                description="Number of pages in duplicate group",
                            ),
                            DiagnosisEvidence(
                                metric_name="canonical_page",
                                source_url=group[0],
                                description="Page this content duplicates",
                            ),
                        ),
                        source_engine=self.source_engine,
                    )
                )
        return tuple(issues)


class KeywordStuffingDiagnosis(DiagnosisRule):
    """Detect potential keyword stuffing."""

    code = "DX_KEYWORD_STUFFING"
    category = DiagnosisCategory.CONTENT
    severity = DiagnosisSeverity.MEDIUM
    priority = DiagnosisPriority.P2
    source_engine = "content_intelligence"
    _THRESHOLD = 0.05

    def evaluate(self, technical, architecture, content_metrics):
        by_url = _content_by_url(content_metrics)
        issues: list[DiagnosisIssue] = []
        for url, m in by_url.items():
            if m.keywords.keyword_stuffing_score > self._THRESHOLD:
                issues.append(
                    DiagnosisIssue(
                        rule_code=self.code,
                        category=self.category,
                        severity=self.severity,
                        priority=self.priority,
                        affected_url=url,
                        explanation=f"Keyword stuffing score is "
                        f"{m.keywords.keyword_stuffing_score:.3f} "
                        f"(threshold: {self._THRESHOLD}). Over-optimized "
                        "keyword density may be flagged as a quality signal.",
                        recommendation="Reduce keyword repetition and focus "
                        "on natural, user-focused content.",
                        evidence=(
                            DiagnosisEvidence(
                                metric_name="keyword_stuffing_score",
                                metric_value=m.keywords.keyword_stuffing_score,
                                threshold=self._THRESHOLD,
                                description="Keyword density deviation score",
                            ),
                        ),
                        source_engine=self.source_engine,
                    )
                )
        return tuple(issues)


class PoorReadabilityDiagnosis(DiagnosisRule):
    """Detect pages with very low readability scores."""

    code = "DX_POOR_READABILITY"
    category = DiagnosisCategory.CONTENT
    severity = DiagnosisSeverity.LOW
    priority = DiagnosisPriority.P3
    source_engine = "content_intelligence"
    _FLESCH_THRESHOLD = 30.0

    def evaluate(self, technical, architecture, content_metrics):
        by_url = _content_by_url(content_metrics)
        issues: list[DiagnosisIssue] = []
        for url, m in by_url.items():
            if m.readability.flesch_reading_ease < self._FLESCH_THRESHOLD:
                issues.append(
                    DiagnosisIssue(
                        rule_code=self.code,
                        category=self.category,
                        severity=self.severity,
                        priority=self.priority,
                        affected_url=url,
                        explanation=f"Flesch reading ease is "
                        f"{m.readability.flesch_reading_ease:.1f} "
                        f"(threshold: {self._FLESCH_THRESHOLD}). Very low "
                        "readability may indicate content that is difficult "
                        "for users to consume.",
                        recommendation="Simplify language, shorten sentences, "
                        "and improve content structure for readability.",
                        evidence=(
                            DiagnosisEvidence(
                                metric_name="flesch_reading_ease",
                                metric_value=m.readability.flesch_reading_ease,
                                threshold=self._FLESCH_THRESHOLD,
                                description="Flesch reading ease score (0-100)",
                            ),
                        ),
                        source_engine=self.source_engine,
                    )
                )
        return tuple(issues)


class StaleContentDiagnosis(DiagnosisRule):
    """Detect content that hasn't been updated in a long time."""

    code = "DX_STALE_CONTENT"
    category = DiagnosisCategory.CONTENT
    severity = DiagnosisSeverity.LOW
    priority = DiagnosisPriority.P3
    source_engine = "content_intelligence"
    _STALE_DAYS = 365

    def evaluate(self, technical, architecture, content_metrics):
        by_url = _content_by_url(content_metrics)
        issues: list[DiagnosisIssue] = []
        for url, m in by_url.items():
            if m.freshness.is_stale:
                days = m.freshness.days_since_modified or m.freshness.days_since_published
                issues.append(
                    DiagnosisIssue(
                        rule_code=self.code,
                        category=self.category,
                        severity=self.severity,
                        priority=self.priority,
                        affected_url=url,
                        explanation=f"Content is approximately {days} days old "
                        "without updates. Stale content may not meet current "
                        "user expectations.",
                        recommendation="Review and update the content to ensure "
                        "it remains accurate and relevant.",
                        evidence=(
                            DiagnosisEvidence(
                                metric_name="days_since_update",
                                metric_value=days or 0,
                                threshold=self._STALE_DAYS,
                                description="Days since last content modification",
                            ),
                        ),
                        source_engine=self.source_engine,
                    )
                )
        return tuple(issues)


# ════════════════════════════════════════════════════════════════════════════
# Cross-engine rule registry
# ════════════════════════════════════════════════════════════════════════════

P0_RULES: list[DiagnosisRule] = [
    MissingTitleDiagnosis(),
    DuplicateTitleDiagnosis(),
    MissingMetaDescriptionDiagnosis(),
    MissingCanonicalDiagnosis(),
    BrokenPageDiagnosis(),
    MissingH1Diagnosis(),
    MultipleH1Diagnosis(),
]

P1_RULES: list[DiagnosisRule] = [
    NoindexDiagnosis(),
    MixedContentDiagnosis(),
    OrphanPageDiagnosis(),
    ThinContentDiagnosis(),
    DuplicateContentDiagnosis(),
]

P2_RULES: list[DiagnosisRule] = [
    MissingStructuredDataDiagnosis(),
    PoorImageAltCoverageDiagnosis(),
    DeadEndPageDiagnosis(),
    ExcessiveCrawlDepthDiagnosis(),
    WeakInternalLinkingDiagnosis(),
    KeywordStuffingDiagnosis(),
]

P3_RULES: list[DiagnosisRule] = [
    PoorReadabilityDiagnosis(),
    StaleContentDiagnosis(),
]

ALL_RULES_BY_PRIORITY: dict[str, list[DiagnosisRule]] = {
    "P0": P0_RULES,
    "P1": P1_RULES,
    "P2": P2_RULES,
    "P3": P3_RULES,
}


def get_rules(priorities: set[str] | None = None) -> list[DiagnosisRule]:
    """Return rules for the requested priority levels."""
    if priorities is None:
        priorities = {"P0", "P1", "P2", "P3"}
    rules: list[DiagnosisRule] = []
    for p in ("P0", "P1", "P2", "P3"):
        if p in priorities:
            rules.extend(ALL_RULES_BY_PRIORITY[p])
    return rules


# ════════════════════════════════════════════════════════════════════════════
# Engine entry point
# ════════════════════════════════════════════════════════════════════════════


def run_diagnosis(
    run_id: str,
    *,
    technical: TechnicalAuditResult | None = None,
    architecture: SiteArchitectureReport | None = None,
    content_metrics: list[ContentMetrics] | None = None,
    priorities: set[str] | None = None,
) -> DiagnosisResult:
    """Run deterministic diagnosis rules across all available engine outputs.

    Each rule inspects the signals it needs and produces :class:`DiagnosisIssue`
    records with evidence, priority, and actionable recommendations.
    """
    rules = get_rules(priorities)
    issues: list[DiagnosisIssue] = []

    for rule in rules:
        rule_issues = rule.evaluate(technical, architecture, content_metrics)
        issues.extend(rule_issues)

    by_priority: dict[str, int] = Counter(i.priority.value for i in issues)
    by_severity: dict[str, int] = Counter(i.severity.value for i in issues)
    by_category: dict[str, int] = Counter(i.category.value for i in issues)

    page_issue_count: Counter[str] = Counter(i.affected_url for i in issues)
    # Exclude site-wide entries from top-affected ranking
    top_affected = tuple(u for u, _ in page_issue_count.most_common(20) if u != "(site-wide)")[:10]

    return DiagnosisResult(
        run_id=run_id,
        total_issues=len(issues),
        issues_by_priority=dict(by_priority),
        issues_by_severity=dict(by_severity),
        issues_by_category=dict(by_category),
        issues=tuple(issues),
        top_affected_pages=top_affected,
    )
