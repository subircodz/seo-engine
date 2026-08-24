"""Search intelligence domain models.

Pure immutable dataclasses for keyword rankings, search queries, datasets,
and competitor observations — zero I/O, zero network, zero LLM deps.

These models are the foundation for Search Intelligence (Phase 6).  They
record *observations* only; no ranking predictions or fabricated data live
here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlparse

__all__ = [
    "CompetitorRanking",
    "RankingObservation",
    "SearchDataset",
    "SearchDevice",
    "SearchIntent",
    "SearchKeyword",
    "SearchQuery",
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


# ════════════════════════════════════════════════════════════════════════════
# Enums
# ════════════════════════════════════════════════════════════════════════════


class SearchIntent(StrEnum):
    """Dominant user intent behind a search query."""

    INFORMATIONAL = "informational"
    NAVIGATIONAL = "navigational"
    COMMERCIAL = "commercial"
    TRANSACTIONAL = "transactional"
    UNKNOWN = "unknown"


class SearchDevice(StrEnum):
    """Device class a search was performed on."""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


# ════════════════════════════════════════════════════════════════════════════
# Validation / normalization helpers
# ════════════════════════════════════════════════════════════════════════════


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalize_keyword(value: str) -> str:
    return " ".join(value.split()).casefold()


def _validate_url(url: str, field_name: str) -> str:
    value = _require_non_empty(url, field_name)
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"{field_name} must be an absolute http(s) URL, got {value!r}")
    return value


def _validate_position(position: int, field_name: str) -> int:
    if isinstance(position, bool) or not isinstance(position, int):
        raise ValueError(f"{field_name} must be an integer, got {position!r}")
    if position < 1:
        raise ValueError(f"{field_name} must be >= 1, got {position}")
    return position


def _validate_count(count: int, field_name: str) -> int:
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError(f"{field_name} must be an integer, got {count!r}")
    if count < 0:
        raise ValueError(f"{field_name} must be >= 0, got {count}")
    return count


# ════════════════════════════════════════════════════════════════════════════
# Keyword
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SearchKeyword:
    """A tracked search keyword with its normalized form and intent.

    ``normalized_keyword`` defaults to a casefolded form with all runs of
    whitespace collapsed to single spaces; pass it explicitly to override.
    """

    keyword: str
    normalized_keyword: str | None = None
    search_intent: SearchIntent = SearchIntent.UNKNOWN

    def __post_init__(self) -> None:
        object.__setattr__(self, "keyword", _require_non_empty(self.keyword, "keyword"))
        if self.normalized_keyword is None:
            object.__setattr__(self, "normalized_keyword", _normalize_keyword(self.keyword))
        else:
            object.__setattr__(
                self,
                "normalized_keyword",
                _normalize_keyword(
                    _require_non_empty(self.normalized_keyword, "normalized_keyword")
                ),
            )


# ════════════════════════════════════════════════════════════════════════════
# Ranking observation
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class RankingObservation:
    """A single observed organic ranking of ``target_url`` for ``keyword``.

    Attributes:
        source: Name of the provider/system that produced this observation
                (e.g. ``"gsc"``, ``"manual"``) — never fabricated.
    """

    keyword: str
    target_url: str
    position: int
    source: str
    search_engine: str = "google"
    country: str = "us"
    language: str = "en"
    device: SearchDevice = SearchDevice.DESKTOP
    observed_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "keyword", _normalize_keyword(_require_non_empty(self.keyword, "keyword"))
        )
        object.__setattr__(self, "target_url", _validate_url(self.target_url, "target_url"))
        object.__setattr__(self, "position", _validate_position(self.position, "position"))
        object.__setattr__(self, "source", _require_non_empty(self.source, "source"))
        object.__setattr__(
            self,
            "search_engine",
            _require_non_empty(self.search_engine, "search_engine").casefold(),
        )
        object.__setattr__(self, "country", _require_non_empty(self.country, "country").casefold())
        object.__setattr__(
            self, "language", _require_non_empty(self.language, "language").casefold()
        )
        if not isinstance(self.observed_at, datetime):
            raise ValueError("observed_at must be a datetime")


# ════════════════════════════════════════════════════════════════════════════
# Search query descriptor
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """Parameters describing *how* a search was (or would be) performed."""

    query: str
    country: str = "us"
    language: str = "en"
    device: SearchDevice = SearchDevice.DESKTOP
    search_engine: str = "google"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "query", _normalize_keyword(_require_non_empty(self.query, "query"))
        )
        object.__setattr__(self, "country", _require_non_empty(self.country, "country").casefold())
        object.__setattr__(
            self, "language", _require_non_empty(self.language, "language").casefold()
        )
        object.__setattr__(
            self,
            "search_engine",
            _require_non_empty(self.search_engine, "search_engine").casefold(),
        )


# ════════════════════════════════════════════════════════════════════════════
# Dataset aggregate
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SearchDataset:
    """An imported collection of search/ranking observations.

    Counts are metadata supplied by the importer; this model does not hold
    the observations themselves (persistence comes later).
    """

    dataset_id: str
    name: str
    source: str
    created_at: datetime = field(default_factory=_utc_now)
    total_keywords: int = 0
    total_observations: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _require_non_empty(self.dataset_id, "dataset_id"))
        object.__setattr__(self, "name", _require_non_empty(self.name, "name"))
        object.__setattr__(self, "source", _require_non_empty(self.source, "source"))
        object.__setattr__(
            self, "total_keywords", _validate_count(self.total_keywords, "total_keywords")
        )
        object.__setattr__(
            self,
            "total_observations",
            _validate_count(self.total_observations, "total_observations"),
        )
        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime")


# ════════════════════════════════════════════════════════════════════════════
# Competitor ranking
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CompetitorRanking:
    """A competitor's observed ranking for one keyword."""

    keyword: str
    competitor_domain: str
    competitor_url: str
    position: int
    observed_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "keyword", _normalize_keyword(_require_non_empty(self.keyword, "keyword"))
        )
        domain = _require_non_empty(self.competitor_domain, "competitor_domain")
        if urlparse(domain).scheme or "/" in domain or any(ch.isspace() for ch in domain):
            raise ValueError(
                f"competitor_domain must be a bare hostname like example.com, got {domain!r}"
            )
        object.__setattr__(self, "competitor_domain", domain.casefold().removeprefix("www."))
        object.__setattr__(
            self, "competitor_url", _validate_url(self.competitor_url, "competitor_url")
        )
        object.__setattr__(self, "position", _validate_position(self.position, "position"))
        if not isinstance(self.observed_at, datetime):
            raise ValueError("observed_at must be a datetime")
