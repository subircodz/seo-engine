"""Distributed cache decorator for provider-neutral search capabilities."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_aio import AIOCitation, AIOverviewObservation, AIOverviewType, CitationSource
from sie.domain.models.search_geo import EntityMention, EntityType, GEOObservation, GenerativeEngineType
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.models.search_serp import SERPFeatureType, SearchSERPFeature
from sie.domain.ports.search_provider import SearchProvider
from sie.infrastructure.search.redis_response_cache import RedisSearchResponseCache
from sie.infrastructure.search.response_cache import CacheKey

__all__ = ["DistributedCacheSearchProvider"]


def _feature_to_dict(feature: SearchSERPFeature) -> dict[str, Any]:
    return {
        "feature_type": feature.feature_type.value,
        "position": feature.position,
        "title": feature.title,
        "url": feature.url,
        "domain": feature.domain,
        "metadata": list(feature.metadata),
    }


def _feature_from_dict(value: dict[str, Any]) -> SearchSERPFeature:
    return SearchSERPFeature(
        feature_type=SERPFeatureType(value["feature_type"]),
        position=value.get("position"),
        title=value.get("title"),
        url=value.get("url"),
        _metadata=tuple(tuple(x) for x in value.get("metadata", [])),
    )


def _search_to_dict(result: SearchResult) -> dict[str, Any]:
    return {
        "keyword": result.keyword,
        "search_engine": result.search_engine,
        "country": result.country,
        "language": result.language,
        "device": result.device.value,
        "items": [
            {
                "position": item.position,
                "title": item.title,
                "url": item.url,
                "serp_features": [_feature_to_dict(f) for f in item.serp_features],
            }
            for item in result.items
        ],
    }


def _search_from_dict(value: dict[str, Any]) -> SearchResult:
    from sie.domain.models.search import SearchDevice

    return SearchResult(
        keyword=value["keyword"],
        search_engine=value["search_engine"],
        country=value["country"],
        language=value["language"],
        device=SearchDevice(value["device"]),
        items=tuple(
            SearchResultItem(
                position=item["position"],
                title=item["title"],
                url=item["url"],
                serp_features=tuple(_feature_from_dict(f) for f in item.get("serp_features", [])),
            )
            for item in value.get("items", [])
        ),
    )


def _aio_to_dict(value: AIOverviewObservation) -> dict[str, Any]:
    return {
        "keyword": value.keyword,
        "ai_type": value.ai_type.value,
        "present": value.present,
        "target_cited": value.target_cited,
        "target_domain": value.target_domain,
        "citation_count": value.citation_count,
        "citations": [
            {
                "domain": c.domain,
                "url": c.url,
                "position": c.position,
                "source_type": c.source_type.value,
                "title": c.title,
            }
            for c in value.citations
        ],
        "competitor_cited_domains": list(value.competitor_cited_domains),
        "observed_at": value.observed_at.isoformat(),
        "source": value.source,
    }


def _aio_from_dict(value: dict[str, Any]) -> AIOverviewObservation:
    return AIOverviewObservation(
        keyword=value["keyword"],
        ai_type=AIOverviewType(value["ai_type"]),
        present=bool(value["present"]),
        target_cited=bool(value.get("target_cited", False)),
        target_domain=value.get("target_domain", ""),
        citation_count=int(value.get("citation_count", 0)),
        citations=tuple(
            AIOCitation(
                domain=c["domain"],
                url=c.get("url", ""),
                position=int(c.get("position", 0)),
                source_type=CitationSource(c.get("source_type", CitationSource.WEB_PAGE.value)),
                title=c.get("title", ""),
            )
            for c in value.get("citations", [])
        ),
        competitor_cited_domains=tuple(value.get("competitor_cited_domains", [])),
        observed_at=datetime.fromisoformat(value["observed_at"]),
        source=value.get("source", "redis-cache"),
    )


def _geo_to_dict(value: GEOObservation) -> dict[str, Any]:
    return {
        "keyword": value.keyword,
        "engine_type": value.engine_type.value,
        "target_mentioned": value.target_mentioned,
        "target_domain": value.target_domain,
        "mention_count": value.mention_count,
        "entity_mentions": [
            {"text": e.text, "entity_type": e.entity_type.value, "is_target": e.is_target, "domain": e.domain}
            for e in value.entity_mentions
        ],
        "competitor_domains": list(value.competitor_domains),
        "citation_urls": list(value.citation_urls),
        "answer_length": value.answer_length,
        "observed_at": value.observed_at.isoformat(),
        "source": value.source,
    }


def _geo_from_dict(value: dict[str, Any]) -> GEOObservation:
    return GEOObservation(
        keyword=value["keyword"],
        engine_type=GenerativeEngineType(value["engine_type"]),
        target_mentioned=bool(value.get("target_mentioned", False)),
        target_domain=value.get("target_domain", ""),
        mention_count=int(value.get("mention_count", 0)),
        entity_mentions=tuple(
            EntityMention(
                text=e["text"],
                entity_type=EntityType(e.get("entity_type", EntityType.BRAND.value)),
                is_target=bool(e.get("is_target", False)),
                domain=e.get("domain", ""),
            )
            for e in value.get("entity_mentions", [])
        ),
        competitor_domains=tuple(value.get("competitor_domains", [])),
        citation_urls=tuple(value.get("citation_urls", [])),
        answer_length=int(value.get("answer_length", 0)),
        observed_at=datetime.fromisoformat(value["observed_at"]),
        source=value.get("source", "redis-cache"),
    )


class DistributedCacheSearchProvider:
    """Adds a shared Redis L2 cache to any ``SearchProvider`` implementation."""

    def __init__(self, provider: SearchProvider, cache: RedisSearchResponseCache) -> None:
        self._provider = provider
        self._cache = cache

    @property
    def supports_aio(self) -> bool:
        return self._provider.supports_aio

    @property
    def supports_geo(self) -> bool:
        return self._provider.supports_geo

    async def search(self, query: SearchQuery) -> SearchResult:
        key = CacheKey.from_query(
            keyword=query.query,
            country=query.country,
            language=query.language,
            device=query.device.value,
            provider=type(self._provider).__name__,
            search_engine=query.search_engine,
        )
        cached = await self._cache.get(key)
        if cached is not None:
            return _search_from_dict(cached)
        result = await self._provider.search(query)
        await self._cache.put(key, _search_to_dict(result))
        return result

    async def extract_aio(self, query: SearchQuery, target_domain: str) -> AIOverviewObservation | None:
        if not self.supports_aio:
            return await self._provider.extract_aio(query, target_domain)
        key = CacheKey.from_query(
            keyword=query.query,
            country=query.country,
            language=query.language,
            device=query.device.value,
            provider=type(self._provider).__name__,
            search_engine=query.search_engine,
        )
        cached = await self._cache.get(key, operation="aio")
        if cached is not None:
            return _aio_from_dict(cached)
        result = await self._provider.extract_aio(query, target_domain)
        if result is not None:
            await self._cache.put(key, _aio_to_dict(result), operation="aio")
        return result

    async def query_geo(self, query: SearchQuery, target_domain: str, engine_type: GenerativeEngineType) -> GEOObservation | None:
        if not self.supports_geo:
            return await self._provider.query_geo(query, target_domain, engine_type)
        key = CacheKey.from_query(
            keyword=query.query,
            country=query.country,
            language=query.language,
            device=query.device.value,
            provider=type(self._provider).__name__,
            search_engine=query.search_engine,
        )
        operation = f"geo:{engine_type.value}"
        cached = await self._cache.get(key, operation=operation)
        if cached is not None:
            return _geo_from_dict(cached)
        result = await self._provider.query_geo(query, target_domain, engine_type)
        if result is not None:
            await self._cache.put(key, _geo_to_dict(result), operation=operation)
        return result

    @property
    def quota(self):
        """Expose the underlying provider quota tracker for observability."""
        return getattr(self._provider, "quota", None)

    async def close(self) -> None:
        close = getattr(self._provider, "close", None)
        if close is not None:
            await close()
        await self._cache.close()
