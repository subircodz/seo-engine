"""SEO Intelligence / Diagnosis domain models.

Pure dataclasses — zero third-party imports.  These represent structured SEO
problems, priorities, evidence, and recommendations produced by the diagnosis
engine.

Language convention: issue descriptions use measured phrasing
("potential ranking issue", "SEO risk", "optimization opportunity",
"technical obstacle") rather than unfounded ranking-impact claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utc_now() -> datetime:
    return datetime.now(UTC)


# ════════════════════════════════════════════════════════════════════════════
# Enums
# ════════════════════════════════════════════════════════════════════════════


class DiagnosisSeverity(StrEnum):
    """How severe the detected issue is."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DiagnosisCategory(StrEnum):
    """Functional area the issue belongs to."""

    META = "meta"
    STRUCTURE = "structure"
    CONTENT = "content"
    LINKS = "links"
    STATUS = "status"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    URL = "url"
    ARCHITECTURE = "architecture"
    STRUCTURED_DATA = "structured_data"


class DiagnosisPriority(StrEnum):
    """Deterministic priority level."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


# ════════════════════════════════════════════════════════════════════════════
# Evidence
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DiagnosisEvidence:
    """Structured evidence supporting a diagnosis issue.

    Attributes:
        metric_name:  Name of the measured metric (e.g. "word_count", "depth").
        metric_value: Actual measured value.
        threshold:    The threshold that was exceeded or not met.
        description:  Human-readable explanation of what was measured.
        source_url:   Additional URL relevant to the evidence (e.g. a
                      duplicate page) — optional.
    """

    metric_name: str
    metric_value: float | int | str | bool | None = None
    threshold: float | int | None = None
    description: str = ""
    source_url: str = ""


# ════════════════════════════════════════════════════════════════════════════
# Diagnosis issue
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DiagnosisIssue:
    """A single structured SEO diagnosis issue.

    Each issue captures the rule that identified it, the affected page,
    supporting evidence, and an actionable recommendation.
    """

    rule_code: str
    category: DiagnosisCategory
    severity: DiagnosisSeverity
    priority: DiagnosisPriority
    affected_url: str
    explanation: str
    recommendation: str
    evidence: tuple[DiagnosisEvidence, ...] = ()
    confidence: float = 1.0  # 0.0-1.0; 1.0 = deterministic detection
    source_engine: str = ""  # which engine surfaced this issue
    detected_at: datetime = field(default_factory=_utc_now)


# ════════════════════════════════════════════════════════════════════════════
# Diagnosis result
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DiagnosisResult:
    """Aggregated diagnosis result for a crawl run."""

    run_id: str
    total_issues: int
    issues_by_priority: dict[str, int]
    issues_by_severity: dict[str, int]
    issues_by_category: dict[str, int]
    issues: tuple[DiagnosisIssue, ...]
    top_affected_pages: tuple[str, ...]
    generated_at: datetime = field(default_factory=_utc_now)
