"""Crawler engine adapters (BFS frontier, robots gate, pacing, dedupe)."""

from sie.infrastructure.crawling.engine import HttpxCrawlerEngine
from sie.infrastructure.crawling.frontier import LRUSet
from sie.infrastructure.crawling.throttle import PerHostRateLimiter

__all__ = ["HttpxCrawlerEngine", "LRUSet", "PerHostRateLimiter"]
