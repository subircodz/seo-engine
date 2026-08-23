"""Parser port — converts raw fetched pages into structured domain models."""

from __future__ import annotations

from typing import Protocol

from sie.domain.models.audit import LinkExtraction, PageDOM
from sie.domain.models.page import FetchedPage


class PageParser(Protocol):
    """Structural contract for HTML→domain-model parsers."""

    def parse_page(self, page: FetchedPage) -> PageDOM: ...

    def parse_links(self, page: FetchedPage) -> LinkExtraction: ...
