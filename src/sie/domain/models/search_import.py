"""Search data import result models.

Immutable value objects describing the outcome of importing externally
supplied CSV/JSON ranking data via ``SearchImportService``.  Rejected rows are
always reported explicitly — bad data is never silently discarded.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sie.domain.models.search import CompetitorRanking, RankingObservation, SearchKeyword

__all__ = ["SearchImportResult", "SearchRecordError"]


@dataclass(frozen=True, slots=True)
class SearchRecordError:
    """A single rejected input record.

    Attributes:
        row_index:  0-based position of the record within the input, or ``-1``
                    for file-level problems (malformed CSV/JSON, missing
                    required columns).
        field:      Offending field name, if attributable to one field.
        reason:     Human-readable explanation of why the record was rejected.
        raw_record: Shallow snapshot of the original row for inspection.
    """

    row_index: int
    reason: str
    field: str = ""
    raw_record: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class SearchImportResult:
    """Structured outcome of one import run.

    Import is all-or-nothing per row: a row is either fully converted into
    validated domain objects or reported in ``errors``.  ``total_rows`` counts
    parsed input records; file-level failures produce a result whose only
    content is a single error (``total_rows == 0``).
    """

    keywords: tuple[SearchKeyword, ...] = ()
    observations: tuple[RankingObservation, ...] = ()
    competitor_rankings: tuple[CompetitorRanking, ...] = ()
    errors: tuple[SearchRecordError, ...] = ()
    total_rows: int = 0

    @property
    def rejected_rows(self) -> int:
        return len(self.errors)

    @property
    def successful_rows(self) -> int:
        return self.total_rows - self.rejected_rows

    @property
    def validation_errors(self) -> tuple[SearchRecordError, ...]:
        return self.errors

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)
