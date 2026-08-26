"""Domain models for audit engines (Technical SEO + Link Graph).

These are pure dataclasses with zero third-party imports — the infrastructure
HTML parser produces them, and both engines consume them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

# ════════════════════════════════════════════════════════════════════════════
# Parsed page (output of the HTML parser)
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class PageImage:
    src: str
    alt: str


@dataclass(frozen=True, slots=True)
class PageDOM:
    """Structured representation of a parsed HTML page."""

    url: str
    status_code: int
    content_type: str | None = None
    html_size: int = 0

    title: str | None = None
    meta_description: str | None = None
    meta_robots: str | None = None
    canonical: str | None = None
    canonicals: tuple[str, ...] = ()

    h1s: tuple[str, ...] = ()
    h2s: tuple[str, ...] = ()
    h3s: tuple[str, ...] = ()

    hreflangs: tuple[tuple[str, str], ...] = ()
    jsonld_types: tuple[str, ...] = ()

    images: tuple[PageImage, ...] = ()
    internal_links: tuple[str, ...] = ()
    external_links: tuple[str, ...] = ()
    nofollow_links: tuple[str, ...] = ()
    mixed_content: bool = False
    query_param_count: int = 0


# ════════════════════════════════════════════════════════════════════════════
# Link extraction
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ExtractedLink:
    target_url: str
    anchor_text: str = ""
    is_internal: bool = True
    rel: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class LinkExtraction:
    """All outgoing links from a single page."""

    source_url: str
    links: tuple[ExtractedLink, ...] = ()


# ════════════════════════════════════════════════════════════════════════════
# Audit context (for cross-page rules)
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AuditContext:
    pages_by_url: Mapping[str, PageDOM]
    link_extractions: Mapping[str, LinkExtraction] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════════════════
# Audit rule protocol and finding
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class AuditFinding:
    rule_code: str
    page_url: str
    severity: str  # critical | warning | info
    message: str
    recommendation: str
    affected_elements: tuple[str, ...] = ()


class AuditRule(Protocol):
    code: str
    severity: str
    category: str
    needs_context: bool

    def check(self, page: PageDOM, context: AuditContext | None) -> AuditFinding | None: ...


# ════════════════════════════════════════════════════════════════════════════
# Audit result
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class TechnicalAuditResult:
    total_pages: int
    total_issues: int
    critical_count: int
    warning_count: int
    info_count: int
    findings: tuple[AuditFinding, ...]
    summary_by_rule: dict[str, int]
    summary_by_severity: dict[str, int]
    top_offending_pages: tuple[str, ...]


# ════════════════════════════════════════════════════════════════════════════
# Link graph models
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class LinkNode:
    url: str
    depth: int
    incoming_count: int
    outgoing_count: int
    pagerank: float


@dataclass(frozen=True, slots=True)
class LinkEdge:
    source_url: str
    target_url: str
    anchor_text: str = ""
    link_type: str = "internal"  # internal | external | nofollow


@dataclass(frozen=True, slots=True)
class LinkGraph:
    nodes: dict[str, LinkNode]
    edges: tuple[LinkEdge, ...]


@dataclass(frozen=True, slots=True)
class LinkVelocity:
    avg_internal_links_per_page: float
    links_by_section: dict[str, int]


@dataclass(frozen=True, slots=True)
class SiteArchitectureReport:
    total_pages: int
    total_internal_links: int
    avg_links_per_page: float
    orphans: tuple[str, ...]
    dead_ends: tuple[str, ...]
    max_depth: int
    avg_depth: float
    depth_distribution: dict[int, int]
    pagerank_top_10: tuple[str, ...]
    pagerank_bottom_10: tuple[str, ...]
    thin_connection_pages: tuple[str, ...]
    link_velocity: LinkVelocity
    pagerank_gini: float | None = None
    pagerank_values: tuple[float, ...] = ()
