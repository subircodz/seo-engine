"""Intelligence service domain models.

Structured output models for LLM-enhanced SEO reasoning.  These are plain
dataclasses with zero third-party imports, following the project convention.

Language convention: all text uses measured phrasing
("potential ranking issue", "SEO risk", "optimization opportunity").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


# ════════════════════════════════════════════════════════════════════════════
# Evidence Package — bounded, structured input for the LLM
# ════════════════════════════════════════════════════════════════════════════

# Maximum items per evidence section to keep the prompt bounded
_MAX_HTTP_PROBLEMS = 20
_MAX_ISSUES_PER_CATEGORY = 10
_MAX_ORPHAN_URLS = 15
_MAX_DEAD_END_URLS = 15
_MAX_TOP_KEYWORDS = 10
_MAX_THIN_URLS = 15
_MAX_DUPLICATE_PAIRS = 10


@dataclass(frozen=True, slots=True)
class CrawlEvidence:
    """Crawl-level statistics derived from the crawl run."""

    total_pages: int
    status_distribution: dict[str, int]  # e.g. {"200": 45, "404": 3, "301": 2}
    http_problems: tuple[dict[str, object], ...] = ()  # [{url, status, message}]


@dataclass(frozen=True, slots=True)
class TechnicalEvidence:
    """Aggregated technical SEO findings."""

    title_missing_count: int = 0
    title_duplicate_count: int = 0
    meta_desc_missing_count: int = 0
    canonical_missing_count: int = 0
    canonical_mismatch_count: int = 0
    h1_missing_count: int = 0
    h1_duplicate_count: int = 0
    robots_noindex_count: int = 0
    mixed_content_count: int = 0
    large_html_count: int = 0
    structured_data_missing_count: int = 0
    hreflang_issues_count: int = 0
    issues_by_rule: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArchitectureEvidence:
    """Link graph and site architecture findings."""

    total_internal_links: int = 0
    avg_links_per_page: float = 0.0
    orphan_count: int = 0
    orphan_urls: tuple[str, ...] = ()
    dead_end_count: int = 0
    dead_end_urls: tuple[str, ...] = ()
    max_depth: int = 0
    avg_depth: float = 0.0
    thin_connection_count: int = 0
    pagerank_top_5: tuple[str, ...] = ()
    pagerank_bottom_5: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContentEvidence:
    """Content intelligence findings."""

    avg_word_count: float = 0.0
    median_word_count: float = 0.0
    thin_content_count: int = 0
    thin_content_urls: tuple[str, ...] = ()
    avg_quality_score: float = 0.0
    quality_distribution: dict[str, int] = field(default_factory=dict)
    duplicate_pair_count: int = 0
    duplicate_pairs: tuple[dict[str, str], ...] = ()  # [{url_a, url_b, status}]
    avg_readability_score: float = 0.0
    images_without_alt_count: int = 0
    total_images: int = 0
    top_keywords: tuple[dict[str, object], ...] = ()  # [{keyword, count, density}]
    keyword_stuffing_count: int = 0


@dataclass(frozen=True, slots=True)
class EvidencePackage:
    """Complete bounded evidence package for LLM reasoning.

    Contains ONLY data actually produced by the existing engines.
    No raw HTML, no unlimited data.  Everything is aggregated and bounded.
    """

    run_id: str
    crawl: CrawlEvidence
    technical: TechnicalEvidence
    architecture: ArchitectureEvidence
    content: ContentEvidence
    diagnosis_issue_count: int = 0
    diagnosis_issues_by_priority: dict[str, int] = field(default_factory=dict)
    diagnosis_issues_by_category: dict[str, int] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════════════════
# LLM Reasoning Output — Phase 5C schema
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class RootCause:
    """A grouped root cause identified by the LLM from related issues."""

    title: str
    evidence: tuple[str, ...]
    confidence: float  # 0.0-1.0


@dataclass(frozen=True, slots=True)
class TopIssue:
    """An important problem identified by the LLM."""

    issue_code: str
    title: str
    interpretation: str
    impact: str
    confidence: float
    affected_url_count: int


@dataclass(frozen=True, slots=True)
class QuickWin:
    """A high-confidence, low-effort fix."""

    action: str
    reason: str
    priority: str  # P0-P3
    difficulty: str  # low/medium/high


@dataclass(frozen=True, slots=True)
class ActionPlanItem:
    """A single recommended action from the LLM action plan."""

    order: int
    action: str
    reason: str
    priority: str  # P0-P3
    difficulty: str  # low/medium/high
    dependencies: tuple[str, ...] = ()


# Keep PriorityIssue for backward compatibility with existing tests
@dataclass(frozen=True, slots=True)
class PriorityIssue:
    """An LLM-interpreted priority issue derived from deterministic evidence."""

    issue_code: str
    interpretation: str
    impact: str
    recommendation: str
    confidence: float  # 0.0-1.0; LLM's self-assessed confidence


@dataclass(frozen=True, slots=True)
class LLMReasoningResult:
    """Full structured output from the LLM reasoning step.

    This is the LLM's interpretation layered on top of the deterministic
    Phase 5A diagnosis.  The deterministic result remains the source of
    truth; this adds human-like reasoning and prioritization.
    """

    run_id: str
    summary: str
    overall_assessment: str
    root_causes: tuple[RootCause, ...]
    top_issues: tuple[TopIssue, ...]
    quick_wins: tuple[QuickWin, ...]
    action_plan: tuple[ActionPlanItem, ...]
    # Legacy fields kept for backward compat
    priority_issues: tuple[PriorityIssue, ...] = ()
    raw_response: str = ""  # original LLM text for audit/debug
    prompt_version: str = ""
    model_name: str = ""
    provider: str = ""
    generated_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class IntelligenceResult:
    """Combined deterministic + LLM reasoning result.

    The ``diagnosis`` field always contains the deterministic Phase 5A result.
    The ``reasoning`` field is ``None`` when the LLM is disabled or failed.
    """

    run_id: str
    diagnosis: object  # DiagnosisResult (avoids circular import)
    reasoning: LLMReasoningResult | None = None
    llm_available: bool = False
    generated_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class IntelligenceReport:
    """Persisted intelligence report — the final deliverable."""

    intelligence_id: str
    run_id: str
    diagnosis_run_id: str
    prompt_version: str
    model_name: str
    provider: str
    summary: str
    overall_assessment: str
    root_causes: tuple[RootCause, ...]
    top_issues: tuple[TopIssue, ...]
    quick_wins: tuple[QuickWin, ...]
    action_plan: tuple[ActionPlanItem, ...]
    raw_response: str = ""
    generated_at: datetime = field(default_factory=_utc_now)
