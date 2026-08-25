"""Generic Evidence and Provenance models for the SEO Intelligence Platform.

Provides a reusable abstraction for evidence supporting findings across all engines:
- SEO/Search
- AIO
- GEO
- Performance
- Entity
- Optimization
- Casino
- Crypto
- Crypto-Casino
- Industry Intelligence
- Reporting

This model supports the provenance chain:
    Observed Data
    ↓
    Evidence
    ↓
    Source / Authority (when available)
    ↓
    Analytical Interpretation
    ↓
    Finding
    ↓
    Recommendation

Language convention: All text uses measured phrasing
("potential ranking issue", "SEO risk", "optimization opportunity")
rather than unfounded ranking-impact claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EvidenceType(StrEnum):
    """Classification of evidence source type."""

    OBSERVED = "observed"
    AUTHORITATIVE = "authoritative"
    ANALYTICAL = "analytical"
    DERIVED = "derived"


class SourceType(StrEnum):
    """Classification of evidence source authority."""

    INTERNAL = "internal"
    EXTERNAL = "external"
    GOOGLE = "google"
    BING = "bing"
    OTHER_ENGINE = "other_engine"
    CONTENT = "content"
    USER_DATA = "user_data"


@dataclass(frozen=True, slots=True)
class Evidence:
    """Generic evidence supporting a finding or observation.

    Represents a single piece of evidence in the provenance chain.
    All fields are immutable and serializable.

    Attributes:
        evidence_type: Classification of evidence (observed, authoritative, etc.)
        source: The data or metric that was observed
        source_type: Classification of the evidence source
        authority: External authority reference (e.g., Google documentation URL)
        confidence: Confidence in this evidence (0.0-1.0); 1.0 = deterministic
        explanation: Human-readable explanation of the evidence
        engine: Which engine produced this evidence
        observed_at: When this evidence was captured
    """

    evidence_type: EvidenceType = EvidenceType.OBSERVED
    source: str = ""
    source_type: SourceType = SourceType.INTERNAL
    authority: str = ""
    confidence: float = 1.0
    explanation: str = ""
    engine: str = ""
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class Provenance:
    """Tracks the origin and transformations of a finding.

    Documents the complete provenance chain for auditability.
    """

    evidence_chain: tuple[Evidence, ...] = ()
    """The chronological chain of evidence leading to this finding."""

    interpretation: str = ""
    """The analytical interpretation applied to the evidence."""

    interpretation_confidence: float = 0.5
    """Confidence in the interpretation (0.0-1.0)."""

    is_authoritative_claim: bool = False
    """Whether this finding claims to be from an authoritative source."""

    methodology: str = ""
    """Description of how findings were derived."""


__all__ = [
    "Evidence",
    "EvidenceType",
    "Provenance",
    "SourceType",
]
