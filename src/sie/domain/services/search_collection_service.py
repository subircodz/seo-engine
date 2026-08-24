"""Search Collection Service (Phase 6H).

Orchestrates ranking collection by delegating each query to a pluggable
``SearchProvider`` and converting the returned ``SearchResult`` items into
domain-native ``RankingObservation`` objects.

Not-ranking handling
--------------------
When a query returns results but the target domain does not appear in the
result list, the service does **not** fabricate a ``RankingObservation``.
Instead it returns a ``CollectionItem`` with ``observation=None`` and
``found=False``.  This preserves the integrity guarantee: every persisted
observation represents a real, observed ranking.

No network, no LLM, no persistence in this module — all I/O is delegated
to the injected provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sie.domain.models.search import RankingObservation, SearchQuery
from sie.domain.models.search_result import SearchResult
from sie.domain.ports.search_provider import SearchProvider

__all__ = ["CollectionItem", "SearchCollectionService"]


@dataclass(frozen=True, slots=True)
class CollectionItem:
    """Outcome of collecting rankings for one ``SearchQuery``.

    ``observation`` is populated when the target domain was found in the
    search results; it is ``None`` when the domain was absent.  Callers
    must never treat ``observation=None`` as a valid ranking position.
    """

    query: SearchQuery
    observation: RankingObservation | None = None
    found: bool = False


class SearchCollectionService:
    """Execute a batch of search queries via a pluggable provider.

    Parameters
    ----------
    provider:
        Any object satisfying the ``SearchProvider`` protocol.
    source:
        Label stored in every produced ``RankingObservation.source`` to
        identify the provenance of the data (e.g. ``"mock-provider"``,
        ``"serpapi"``).
    """

    def __init__(self, provider: SearchProvider, *, source: str = "search-provider") -> None:
        self._provider = provider
        self._source = source

    async def collect(self, queries: list[SearchQuery]) -> list[CollectionItem]:
        """Collect rankings for each query.

        Returns one ``CollectionItem`` per query, preserving the input
        ordering.  Provider errors propagate directly to the caller so they
        can decide whether to retry, skip, or abort.
        """
        items: list[CollectionItem] = []
        for query in queries:
            result = await self._provider.search(query)
            item = self._build_item(query, result)
            items.append(item)
        return items

    def _build_item(self, query: SearchQuery, result: SearchResult) -> CollectionItem:
        """Map a ``SearchResult`` into a ``CollectionItem``.

        If the target domain is present, the first matching item's position
        is used for the ``RankingObservation``.  If the domain is absent,
        ``observation`` is ``None``.
        """
        if query.target_domain is None:
            # No target to look for; record as not-found.
            return CollectionItem(query=query, observation=None, found=False)

        target = query.target_domain.casefold()
        for item in result.items:
            if item.domain == target:
                observation = RankingObservation(
                    keyword=query.query,
                    target_url=item.url,
                    position=item.position,
                    source=self._source,
                    search_engine=query.search_engine,
                    country=query.country,
                    language=query.language,
                    device=query.device,
                    observed_at=datetime.now(UTC),
                )
                return CollectionItem(query=query, observation=observation, found=True)

        return CollectionItem(query=query, observation=None, found=False)
