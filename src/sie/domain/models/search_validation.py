"""Search dataset validation models.

Immutable value objects describing the outcome of validating and normalizing
an imported search dataset (``SearchDatasetService``).  Issues are always
reported explicitly — conflicting records are flagged, never silently resolved.
"""

from __future__ import annotations

from dataclasses import dataclass

from sie.domain.models.search import CompetitorRanking, RankingObservation, SearchKeyword
from sie.domain.models.search_import import SearchImportResult

__all__ = [
    "DatasetValidationIssue",
    "DatasetValidationResult",
    "SearchDatasetContent",
]

# Severity levels used by ``DatasetValidationIssue.severity``.
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# Issue codes emitted by ``SearchDatasetService``.
EMPTY_DATASET = "empty_dataset"
INVALID_KEYWORD = "invalid_keyword"
INVALID_OBSERVATION = "invalid_observation"
INVALID_POSITION = "invalid_position"
INVALID_COMPETITOR_RANKING = "invalid_competitor_ranking"
NEGATIVE_COUNT = "negative_count"
DUPLICATE_OBSERVATION = "duplicate_observation"
CONFLICTING_OBSERVATION = "conflicting_observation"
DUPLICATE_COMPETITOR_RANKING = "duplicate_competitor_ranking"
CONFLICTING_COMPETITOR_RANKING = "conflicting_competitor_ranking"
INCONSISTENT_KEYWORD_NORMALIZATION = "inconsistent_keyword_normalization"
KEYWORD_COLLISION = "keyword_collision"
MALFORMED_URL = "malformed_url"
NON_HTTPS_URL = "non_https_url"
MISSING_COMPETITOR_DOMAIN = "missing_competitor_domain"
MISSING_COMPETITOR_URL = "missing_competitor_url"


@dataclass(frozen=True, slots=True)
class DatasetValidationIssue:
    """A single problem found while validating a dataset."""

    code: str
    severity: str
    message: str
    keyword: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetValidationResult:
    """Structured outcome of one dataset validation run.

    ``valid`` is ``True`` when no ``error``-severity issues were found;
    warnings (e.g. harmless duplicates) do not invalidate a dataset on their
    own.
    """

    valid: bool
    total_records: int
    issue_count: int
    issues: tuple[DatasetValidationIssue, ...]


@dataclass(frozen=True, slots=True)
class SearchDatasetContent:
    """The record payload belonging to one ``SearchDataset``.

    ``SearchDataset`` itself carries only metadata and counts (a deliberate
    Phase 6A decision); this bundle pairs it with the imported records so the
    validation service can inspect them without mutating anything.
    """

    keywords: tuple[SearchKeyword, ...] = ()
    observations: tuple[RankingObservation, ...] = ()
    competitor_rankings: tuple[CompetitorRanking, ...] = ()

    @classmethod
    def from_import_result(cls, result: SearchImportResult) -> SearchDatasetContent:
        """Build content from a successful Phase 6B import."""
        return cls(
            keywords=result.keywords,
            observations=result.observations,
            competitor_rankings=result.competitor_rankings,
        )
