"""Search Collection Service (Phase 6H/6I).

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

from sie.domain.models.search import RankingObservation, SearchDataset, SearchQuery
from sie.domain.models.search_result import SearchCollectionResult, SearchResult
from sie.domain.ports.persistence import CrawlRunRepository
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
    repository:
        Any object satisfying the ``CrawlRunRepository`` protocol, used by
        ``collect_and_persist`` to validate dataset existence and save
        observations.
    source:
        Label stored in every produced ``RankingObservation.source`` to
        identify the provenance of the data (e.g. ``"mock-provider"``,
        ``"serpapi"``).
    """

    def __init__(
        self,
        provider: SearchProvider,
        *,
        repository: CrawlRunRepository | None = None,
        source: str = "search-provider",
    ) -> None:
        self._provider = provider
        self._repository = repository
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

    async def collect_and_persist(
        self,
        dataset_id: str,
        queries: list[SearchQuery],
    ) -> SearchCollectionResult:
        """Collect rankings and persist found observations into *dataset_id*.

        Flow:
        1. Validate the dataset exists in the repository.
        2. Execute each query through the provider.
        3. Persist only actual ``RankingObservation`` objects (not-found
           queries produce no persisted rows).
        4. Return a ``SearchCollectionResult`` summarising the outcome.

        Provider errors on individual queries are captured as
        ``collection_errors`` strings and do not abort the remaining queries.
        """
        if self._repository is None:
            raise RuntimeError("collect_and_persist requires a repository")

        stored = await self._repository.get_search_dataset(dataset_id)
        if stored is None:
            # Site analysis owns its short-lived ranking dataset and must
            # initialize it before the collection service can persist rows.
            # Other callers retain the strict missing-dataset contract.
            if self._source == "site-analysis":
                await self._repository.save_search_dataset(
                    SearchDataset(
                        dataset_id=dataset_id,
                        name=f"Site Analysis: {dataset_id.removeprefix('site-')}",
                        source="site-analysis",
                        created_at=datetime.now(UTC),
                        total_keywords=len(queries),
                        total_observations=0,
                    )
                )
            else:
                raise LookupError(f"Dataset '{dataset_id}' not found")

        items: list[CollectionItem] = []
        errors: list[str] = []
        for query in queries:
            try:
                result = await self._provider.search(query)
                items.append(self._build_item(query, result))
            except Exception as exc:
                errors.append(f"Query '{query.query}' failed: {exc}")

        observations = [item.observation for item in items if item.observation is not None]
        saved = 0
        if observations:
            saved = await self._repository.save_search_observations(dataset_id, observations)

        ranked = sum(1 for item in items if item.found)
        return SearchCollectionResult(
            dataset_id=dataset_id,
            queried_count=len(queries),
            ranked_count=ranked,
            not_ranking_count=len(items) - ranked,
            observations_saved=saved,
            collection_errors=tuple(errors),
        )

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
