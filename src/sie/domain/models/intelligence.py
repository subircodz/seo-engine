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


@dataclass(frozen=True, slots=True)
class PriorityIssue:
    """An LLM-interpreted priority issue derived from deterministic evidence."""

    issue_code: str
    interpretation: str
    impact: str
    recommendation: str
    confidence: float  # 0.0-1.0; LLM's self-assessed confidence


@dataclass(frozen=True, slots=True)
class ActionPlanItem:
    """A single recommended action from the LLM action plan."""

    priority: str
    action: str
    reason: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LLMReasoningResult:
    """Full structured output from the LLM reasoning step.

    This is the LLM's interpretation layered on top of the deterministic
    Phase 5A diagnosis.  The deterministic result remains the source of
    truth; this adds human-like reasoning and prioritization.
    """

    run_id: str
    summary: str
    priority_issues: tuple[PriorityIssue, ...]
    action_plan: tuple[ActionPlanItem, ...]
    raw_response: str = ""  # original LLM text for audit/debug
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
