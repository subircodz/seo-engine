"""AI Overview (AIO) intelligence domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from sie.domain.models.search_surface import EvidenceProvenance, ObservationKind


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AIOverviewType(StrEnum):
    AI_OVERVIEW = "ai_overview"
    COPILOT = "copilot"
    PERPLEXITY = "perplexity"
    CHATGPT_SEARCH = "chatgpt_search"
    OTHER = "other"


class CitationSource(StrEnum):
    WEB_PAGE = "web_page"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    NEWS = "news"
    VIDEO = "video"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class AIOCitation:
    domain: str
    url: str = ""
    position: int = 0
    source_type: CitationSource = CitationSource.WEB_PAGE
    title: str = ""

    def __post_init__(self) -> None:
        if not self.domain or not self.domain.strip():
            raise ValueError("domain must be a non-empty string")
        normalised = self.domain.casefold().removeprefix("www.").strip()
        if normalised != self.domain:
            object.__setattr__(self, "domain", normalised)
        if self.position < 0:
            raise ValueError("position cannot be negative")


@dataclass(frozen=True, slots=True)
class AIOverviewObservation:
    """One AIO observation with explicit evidence provenance."""

    keyword: str
    ai_type: AIOverviewType
    present: bool
    target_cited: bool = False
    target_domain: str = ""
    citation_count: int = 0
    citations: tuple[AIOCitation, ...] = ()
    competitor_cited_domains: tuple[str, ...] = ()
    observed_at: datetime = field(default_factory=_utc_now)
    source: str = "manual"
    provenance: EvidenceProvenance | None = None

    def __post_init__(self) -> None:
        if not self.keyword or not self.keyword.strip():
            raise ValueError("keyword must be a non-empty string")
        object.__setattr__(self, "keyword", " ".join(self.keyword.split()).casefold())
        if self.target_domain:
            object.__setattr__(
                self, "target_domain", self.target_domain.casefold().removeprefix("www.").strip()
            )
        if self.citation_count < 0:
            raise ValueError("citation_count cannot be negative")
        if self.provenance is None:
            object.__setattr__(
                self,
                "provenance",
                EvidenceProvenance(
                    provider_name=self.source,
                    observation_kind=ObservationKind.MANUAL,
                    retrieved_at=self.observed_at,
                ),
            )


@dataclass(frozen=True, slots=True)
class AIOverviewMetrics:
    keyword: str
    observation_count: int
    ai_overview_present_count: int
    target_cited_count: int
    competitor_cited_count: int
    citation_rate: float
    target_citation_rate: float


@dataclass(frozen=True, slots=True)
class AIOverviewDatasetMetrics:
    dataset_id: str
    total_keywords: int
    keywords_with_ai_overview: int
    keywords_target_cited: int
    total_ai_overview_observations: int
    total_citations: int
    target_citation_rate: float
    competitor_cited_domains: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIOverviewResult:
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
]
