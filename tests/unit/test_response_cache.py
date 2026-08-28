from __future__ import annotations

from sie.infrastructure.search.response_cache import CacheKey, SearchResponseCache


def test_cache_key_separates_target_context() -> None:
    first = CacheKey.from_query("seo", "us", "en", "desktop", "serpapi", context="aio:example.com")
    second = CacheKey.from_query("seo", "us", "en", "desktop", "serpapi", context="aio:other.com")
    assert first.hash() != second.hash()


def test_lru_cache_expires_and_tracks_hits() -> None:
    cache = SearchResponseCache(max_entries=2, ttl_seconds=60)
    key = CacheKey.from_query("seo", "us", "en", "desktop", "serpapi")
    cache.put(key, {"value": 1})
    assert cache.get(key) == {"value": 1}
    assert cache.stats["hits"] == 1
    assert cache.stats["misses"] == 0
