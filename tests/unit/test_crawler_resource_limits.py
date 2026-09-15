"""Crawler resource-boundary regression tests."""

from collections import deque

from sie.domain.models.crawl import CrawlPolicy
from sie.infrastructure.crawling.engine import HttpxCrawlerEngine, _RunState
from sie.infrastructure.crawling.frontier import LRUSet


def test_enqueue_never_grows_frontier_beyond_max_pages() -> None:
    policy = CrawlPolicy(max_pages=3)
    state = _RunState(
        policy=policy,
        seed_url="https://example.com/",
        frontier=deque(),
        visited=LRUSet(100),
    )

    HttpxCrawlerEngine._enqueue(
        state,
        [
            ("https://example.com/1", 1, state.seed_url),
            ("https://example.com/2", 1, state.seed_url),
            ("https://example.com/3", 1, state.seed_url),
            ("https://example.com/4", 1, state.seed_url),
            ("https://example.com/5", 1, state.seed_url),
        ],
    )

    assert state.discovered == 3
    assert len(state.frontier) == 3
    assert list(state.frontier) == [
        ("https://example.com/1", 1, state.seed_url),
        ("https://example.com/2", 1, state.seed_url),
        ("https://example.com/3", 1, state.seed_url),
    ]


def test_enqueue_does_not_add_more_after_page_budget_is_exhausted() -> None:
    policy = CrawlPolicy(max_pages=2)
    state = _RunState(
        policy=policy,
        seed_url="https://example.com/",
        frontier=deque(),
        visited=LRUSet(100),
        discovered=2,
    )

    HttpxCrawlerEngine._enqueue(
        state,
        [("https://example.com/new", 1, state.seed_url)],
    )

    assert state.discovered == 2
    assert len(state.frontier) == 0
