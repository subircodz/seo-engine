"""Mock search provider for testing and development (Phase 6H + AIO/GEO).

Returns pre-configured ``SearchResult`` objects without any network I/O.
Never performs real search requests.  Useful for unit tests, integration
tests, and local development.

Extended with optional AIO/GEO observation fixtures for deterministic testing.
"""

from __future__ import annotations

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_aio import AIOverviewObservation
from sie.domain.models.search_geo import GenerativeEngineType, GEOObservation
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
    aio_observations:
        Optional mapping from keyword to ``AIOverviewObservation`` for AIO testing.
    geo_observations:
        Optional mapping from (keyword, engine_type) to ``GEOObservation`` for GEO testing.
    """

    def __init__(
        self,
        results: dict[str, SearchResult] | None = None,
        aio_observations: dict[str, AIOverviewObservation] | None = None,
        geo_observations: dict[tuple[str, GenerativeEngineType], GEOObservation] | None = None,
    ) -> None:
        self._results: dict[str, SearchResult] = dict(results) if results else {}
        self._aio_observations: dict[str, AIOverviewObservation] = (
            dict(aio_observations) if aio_observations else {}
        )
        self._geo_observations: dict[tuple[str, GenerativeEngineType], GEOObservation] = (
            dict(geo_observations) if geo_observations else {}
        )
        self._calls: list[SearchQuery] = []
        self._aio_calls: list[tuple[SearchQuery, str]] = []
        self._geo_calls: list[tuple[SearchQuery, str, GenerativeEngineType]] = []

    @property
    def supports_aio(self) -> bool:
        """Mock provider supports AIO if fixtures are provided."""
        return bool(self._aio_observations)

    @property
    def supports_geo(self) -> bool:
        """Mock provider supports GEO if fixtures are provided."""
        return bool(self._geo_observations)

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

    async def extract_aio(
        self, query: SearchQuery, target_domain: str
    ) -> AIOverviewObservation | None:
        """Return pre-configured AIO observation for testing."""
        self._aio_calls.append((query, target_domain))
        if not self._aio_observations:
            return None
        return self._aio_observations.get(query.query)

    async def query_geo(
        self, query: SearchQuery, target_domain: str, engine_type: GenerativeEngineType
    ) -> GEOObservation | None:
        """Return pre-configured GEO observation for testing."""
        self._geo_calls.append((query, target_domain, engine_type))
        if not self._geo_observations:
            return None
        return self._geo_observations.get((query.query, engine_type))

    @property
    def calls(self) -> list[SearchQuery]:
        """Return the list of queries that have been submitted (for assertions)."""
        return list(self._calls)

    @property
    def aio_calls(self) -> list[tuple[SearchQuery, str]]:
        """Return the list of AIO extraction calls."""
        return list(self._aio_calls)

    @property
    def geo_calls(self) -> list[tuple[SearchQuery, str, GenerativeEngineType]]:
        """Return the list of GEO query calls."""
        return list(self._geo_calls)
