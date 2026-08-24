"""Mock search provider for testing and development (Phase 6H).

Returns pre-configured ``SearchResult`` objects without any network I/O.
Never performs real search requests.  Useful for unit tests, integration
tests, and local development.
"""

from __future__ import annotations

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_result import SearchResult

__all__ = ["MockSearchProvider"]


class MockSearchProvider:
    """In-memory search provider backed by a keyword-to-result mapping.

    Parameters
    ----------
    results:
        Mapping from *normalized* keyword strings to ``SearchResult`` objects.
        Keys are matched case-insensitively after normalization (same rules as
        ``SearchQuery.query``).
    """

    def __init__(self, results: dict[str, SearchResult] | None = None) -> None:
        self._results: dict[str, SearchResult] = dict(results) if results else {}
        self._calls: list[SearchQuery] = []

    async def search(self, query: SearchQuery) -> SearchResult:
        """Return the pre-configured result for ``query``.

        Raises ``KeyError`` with a clear message if no result is configured
        for the query's keyword.
        """
        self._calls.append(query)
        result = self._results.get(query.query)
        if result is None:
            raise KeyError(
                f"MockSearchProvider has no result configured for keyword {query.query!r}"
            )
        return result

    @property
    def calls(self) -> list[SearchQuery]:
        """Return the list of queries that have been submitted (for assertions)."""
        return list(self._calls)
