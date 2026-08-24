"""AI Overview (AIO) intelligence domain models (Phase 6N-F).

Immutable value objects representing observations of AI-generated search
answers (AI Overviews, AI snippets, LLM-powered search results).

These models are provider-neutral and capture only the essential,
vendor-neutral aspects of AI search observations.  Provider-specific
details (Google AI Overview vs Bing Copilot vs Perplexity) are normalised
to common enums and fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AIOverviewType(StrEnum):
    """Types of AI-generated search answers."""

    AI_OVERVIEW = "ai_overview"
    """Google AI Overview (formerly SGE)."""

    COPILOT = "copilot"
    """Bing Copilot / Microsoft AI answer."""

    PERPLEXITY = "perplexity"
    """Perplexity AI answer."""

    CHATGPT_SEARCH = "chatgpt_search"
    """ChatGPT search answer."""

    OTHER = "other"
    """Catch-all for emerging AI answer types."""


class CitationSource(StrEnum):
    """Source type of a citation within an AI answer."""

    WEB_PAGE = "web_page"
    """Citation to a standard web page."""

    KNOWLEDGE_GRAPH = "knowledge_graph"
    """Citation to a knowledge graph entity."""

    NEWS = "news"
    """Citation to a news article."""

    VIDEO = "video"
    """Citation to a video source."""

    OTHER = "other"
    """Other citation source type."""


@dataclass(frozen=True, slots=True)
class AIOCitation:
    """A single citation/source referenced within an AI-generated answer.

    Provider-neutral: captures only the citation's domain, URL, and
    position within the answer, without coupling to a specific AI provider.
    """

    domain: str
    """Bare, casefolded hostname of the cited source."""

    url: str = ""
    """Full URL of the cited source, if available."""

    position: int = 0
    """Position of this citation within the AI answer (0 = first)."""

    source_type: CitationSource = CitationSource.WEB_PAGE
    """Type of the cited source."""

    title: str = ""
    """Title of the cited source, if available."""

    def __post_init__(self) -> None:
        if not self.domain or not self.domain.strip():
            raise ValueError("domain must be a non-empty string")
        # Normalise domain
        normalised = self.domain.casefold().removeprefix("www.").strip()
        if normalised != self.domain:
            object.__setattr__(self, "domain", normalised)


@dataclass(frozen=True, slots=True)
class AIOverviewObservation:
    """A single observation of an AI-generated search answer for a keyword.

    Records the presence/absence of an AI overview, whether the target
    domain is cited, and which competitors appear.  All fields are
    provider-neutral.
    """

    keyword: str
    """The search query / keyword observed."""

    ai_type: AIOverviewType
    """Type of AI answer observed."""

    present: bool
    """Whether an AI overview was present for this keyword."""

    target_cited: bool = False
    """Whether the target domain is cited in the AI answer."""

    target_domain: str = ""
    """The target domain being tracked (for citation matching)."""

    citation_count: int = 0
    """Total number of citations in the AI answer."""

    citations: tuple[AIOCitation, ...] = ()
    """Citations within the AI answer, if available."""

    competitor_cited_domains: tuple[str, ...] = ()
    """Competitor domains cited in the AI answer."""

    observed_at: datetime = field(default_factory=_utc_now)
    """When this observation was recorded."""

    source: str = "manual"
    """Provider/system that produced this observation."""

    def __post_init__(self) -> None:
        if not self.keyword or not self.keyword.strip():
            raise ValueError("keyword must be a non-empty string")
        # Normalise keyword
        normalised = " ".join(self.keyword.split()).casefold()
        if normalised != self.keyword:
            object.__setattr__(self, "keyword", normalised)
        # Normalise target domain
        if self.target_domain:
            norm_domain = self.target_domain.casefold().removeprefix("www.").strip()
            if norm_domain != self.target_domain:
                object.__setattr__(self, "target_domain", norm_domain)


@dataclass(frozen=True, slots=True)
class AIOverviewMetrics:
    """Aggregated AIO metrics for a single keyword across observations."""

    keyword: str
    observation_count: int
    ai_overview_present_count: int
    target_cited_count: int
    competitor_cited_count: int
    citation_rate: float
    """Fraction of observations where AI overview was present (0.0-1.0)."""
    target_citation_rate: float
    """Fraction of AI-present observations where target was cited (0.0-1.0)."""


@dataclass(frozen=True, slots=True)
class AIOverviewDatasetMetrics:
    """Dataset-wide AIO aggregate metrics."""

    dataset_id: str
    total_keywords: int
    keywords_with_ai_overview: int
    keywords_target_cited: int
    total_ai_overview_observations: int
    total_citations: int
    target_citation_rate: float
    """Fraction of AI-present keywords where target is cited (0.0-1.0)."""
    competitor_cited_domains: tuple[str, ...] = ()
    """All unique competitor domains cited across all observations."""


@dataclass(frozen=True, slots=True)
class AIOverviewResult:
    """Complete AIO analysis result for a dataset."""

    dataset_id: str
    keyword_metrics: tuple[AIOverviewMetrics, ...]
    dataset_metrics: AIOverviewDatasetMetrics


__all__ = [
    "AIOCitation",
    "AIOverviewDatasetMetrics",
    "AIOverviewMetrics",
    "AIOverviewObservation",
    "AIOverviewResult",
    "AIOverviewType",
    "CitationSource",
]
