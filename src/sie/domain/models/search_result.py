"""Provider-neutral search result models (Phase 6H).

Immutable value objects returned by ``SearchProvider`` implementations.
These models are intentionally generic — no vendor-specific fields are
allowed so domain code never couples to a particular search API.

URL validation and position constraints mirror the rules established in
``sie.domain.models.search`` for consistency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from sie.domain.models.search import SearchDevice

__all__ = [
    "SearchCollectionResult",
    "SearchResult",
    "SearchResultItem",
]


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


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


def _extract_domain(url: str) -> str:
    """Extract a bare, casefolded hostname from a URL, stripping ``www.``."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").split(":")[0].casefold()
    if host.startswith("www."):
        host = host[4:]
    return host


# ════════════════════════════════════════════════════════════════════════════
# Result item
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SearchResultItem:
    """A single organic search result returned by a provider.

    ``domain`` is derived automatically from ``url``; it is always a bare,
    casefolded hostname with ``www.`` stripped.  The model enforces:
    - position >= 1
    - URL must be http/https
    """

    position: int
    title: str
    url: str
    domain: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", _validate_position(self.position, "position"))
        object.__setattr__(self, "title", _require_non_empty(self.title, "title"))
        object.__setattr__(self, "url", _validate_url(self.url, "url"))
        object.__setattr__(self, "domain", _extract_domain(self.url))


# ════════════════════════════════════════════════════════════════════════════
# Result aggregate
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SearchResult:
    """An ordered collection of search results for a single query.

    ``items`` is always a tuple (immutable).  Providers must supply results
    in deterministic order; consumers should not re-order them.
    """

    keyword: str
    search_engine: str = "google"
    country: str = "us"
    language: str = "en"
    device: SearchDevice = SearchDevice.DESKTOP
    items: tuple[SearchResultItem, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "keyword", _require_non_empty(self.keyword, "keyword"))
        object.__setattr__(
            self,
            "search_engine",
            _require_non_empty(self.search_engine, "search_engine").casefold(),
        )
        object.__setattr__(self, "country", _require_non_empty(self.country, "country").casefold())
        object.__setattr__(
            self, "language", _require_non_empty(self.language, "language").casefold()
        )
        if not isinstance(self.items, tuple):
            raise ValueError(f"items must be a tuple, got {type(self.items).__name__}")


# ════════════════════════════════════════════════════════════════════════════
# Collection result
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class SearchCollectionResult:
    """Structured outcome of a batch collection run.

    ``queried_count`` is the total number of queries submitted.
    ``ranked_count`` is how many returned a result where the target domain
    appeared.  ``not_ranking_count`` is the remainder where the target was
    absent from the results.  ``observations_saved`` is how many
    ``RankingObservation`` objects were persisted (always <= ranked_count
    when some are filtered or deduplicated).  ``collection_errors`` holds
    human-readable messages for any query that failed at the provider level.
    """

    dataset_id: str
    queried_count: int = 0
    ranked_count: int = 0
    not_ranking_count: int = 0
    observations_saved: int = 0
    collection_errors: tuple[str, ...] = ()
