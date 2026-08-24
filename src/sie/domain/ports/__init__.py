"""Ports: abstract contracts for external capabilities.

Consumers depend on these Protocols; concrete providers live in
``sie.infrastructure`` and are injected at the composition root.
"""

from sie.domain.ports.crawling import Crawler
from sie.domain.ports.fetching import Fetcher
from sie.domain.ports.llm import LLMProvider
from sie.domain.ports.persistence import CrawlRunRepository
from sie.domain.ports.rendering import Renderer

__all__ = ["CrawlRunRepository", "Crawler", "Fetcher", "LLMProvider", "Renderer"]
