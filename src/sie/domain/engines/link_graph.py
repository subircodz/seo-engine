"""Link graph engine — builds site architecture from crawl + link extraction data.

Pure functions, no I/O.  Takes domain models (:class:`FetchedPage`,
:class:`LinkExtraction`) and returns :class:`LinkGraph` /
:class:`SiteArchitectureReport`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from urllib.parse import urlsplit

from sie.domain.models.audit import (
    LinkEdge,
    LinkExtraction,
    LinkGraph,
    LinkNode,
    LinkVelocity,
    SiteArchitectureReport,
)
from sie.domain.models.page import FetchedPage

# ════════════════════════════════════════════════════════════════════════════
# Graph construction
# ════════════════════════════════════════════════════════════════════════════


def build_link_graph(
    pages: list[FetchedPage],
    link_extractions: dict[str, LinkExtraction],
    base_domain: str = "",
) -> LinkGraph:
    """Build a directed graph from crawled pages and their extracted links."""
    if not base_domain and pages:
        base_domain = (urlsplit(pages[0].url).hostname or "").lower()

    nodes: dict[str, LinkNode] = {}
    edges: list[LinkEdge] = []
    incoming_count: Counter[str] = Counter()
    outgoing_count: Counter[str] = Counter()

    for page in pages:
        nodes[page.url] = LinkNode(
            url=page.url,
            depth=page.depth,
            incoming_count=0,
            outgoing_count=0,
            pagerank=0.0,
        )

    for page in pages:
        le = link_extractions.get(page.url)
        if le is None:
            continue
        for link in le.links:
            link_type = (
                "nofollow"
                if "nofollow" in link.rel
                else ("internal" if link.is_internal else "external")
            )
            edges.append(
                LinkEdge(
                    source_url=page.url,
                    target_url=link.target_url,
                    anchor_text=link.anchor_text,
                    link_type=link_type,
                )
            )
            outgoing_count[page.url] += 1
            if link.is_internal:
                incoming_count[link.target_url] += 1

    for url, node in nodes.items():
        nodes[url] = LinkNode(
            url=node.url,
            depth=node.depth,
            incoming_count=incoming_count.get(url, 0),
            outgoing_count=outgoing_count.get(url, 0),
            pagerank=0.0,
        )

    return LinkGraph(nodes=nodes, edges=tuple(edges))


# ════════════════════════════════════════════════════════════════════════════
# PageRank
# ════════════════════════════════════════════════════════════════════════════


def compute_pagerank(
    graph: LinkGraph,
    damping: float = 0.85,
    max_iterations: int = 100,
    threshold: float = 1e-6,
) -> dict[str, float]:
    """Iterative PageRank (handles dangling nodes via uniform redistribution)."""
    n = len(graph.nodes)
    if n == 0:
        return {}

    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing_count: dict[str, int] = {}
    for url, node in graph.nodes.items():
        outgoing_count[url] = node.outgoing_count
    for edge in graph.edges:
        if edge.target_url in graph.nodes and edge.link_type == "internal":
            incoming[edge.target_url].append(edge.source_url)

    dangling = [u for u, c in outgoing_count.items() if c == 0]
    pr = {url: 1.0 / n for url in graph.nodes}

    for _ in range(max_iterations):
        dangling_sum = sum(pr[u] for u in dangling)
        new_pr: dict[str, float] = {}
        for url in graph.nodes:
            link_sum = sum(
                pr[src] / outgoing_count[src]
                for src in incoming[url]
                if outgoing_count.get(src, 0) > 0
            )
            new_pr[url] = (1 - damping) / n + damping * (link_sum + dangling_sum / n)
        diff = sum(abs(new_pr[u] - pr[u]) for u in graph.nodes)
        pr = new_pr
        if diff < threshold:
            break

    return pr


# ════════════════════════════════════════════════════════════════════════════
# Analysis helpers
# ════════════════════════════════════════════════════════════════════════════


def find_orphan_pages(graph: LinkGraph) -> tuple[str, ...]:
    """Pages with no incoming internal links (and are not the root)."""
    return tuple(url for url, node in graph.nodes.items() if node.incoming_count == 0)


def find_dead_end_pages(graph: LinkGraph) -> tuple[str, ...]:
    """Pages with no outgoing internal links."""
    return tuple(url for url, node in graph.nodes.items() if node.outgoing_count == 0)


def find_depth_outliers(graph: LinkGraph, max_depth: int = 5) -> tuple[str, ...]:
    """Pages deeper than *max_depth* clicks from the root."""
    return tuple(url for url, node in graph.nodes.items() if node.depth > max_depth)


def identify_thin_pages(graph: LinkGraph, threshold: int = 2) -> tuple[str, ...]:
    """Pages with few incoming + outgoing connections (under-connected)."""
    return tuple(
        url
        for url, node in graph.nodes.items()
        if (node.incoming_count + node.outgoing_count) <= threshold
    )


def compute_link_velocity(graph: LinkGraph) -> LinkVelocity:
    """Internal link density by URL section (first path segment)."""
    internal_edges = [e for e in graph.edges if e.link_type == "internal"]
    section_counts: Counter[str] = Counter()
    for edge in internal_edges:
        section = urlsplit(edge.source_url).path.split("/")[1] or "/"
        section_counts[section] += 1

    total_pages = len(graph.nodes)
    avg = len(internal_edges) / total_pages if total_pages else 0.0
    return LinkVelocity(
        avg_internal_links_per_page=round(avg, 2),
        links_by_section=dict(section_counts.most_common(50)),
    )


# ════════════════════════════════════════════════════════════════════════════
# Full architecture report
# ════════════════════════════════════════════════════════════════════════════


def compute_gini(values: tuple[float, ...]) -> float | None:
    """Compute Gini coefficient for a distribution of values.

    0.0 = perfectly equal (every page has same internal authority)
    1.0 = maximally unequal (one page has all authority)
    None = insufficient data (<3 values or all zero)
    """
    if len(values) < 3 or sum(values) == 0:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cumulative = 0.0
    for i, val in enumerate(sorted_vals):
        cumulative += (2 * (i + 1) - n - 1) * val
    return round(cumulative / (n * sum(sorted_vals)), 4)


def build_architecture_report(
    pages: list[FetchedPage],
    link_extractions: dict[str, LinkExtraction],
    max_depth_for_analysis: int = 10,
    pagerank_damping: float = 0.85,
    pagerank_max_iterations: int = 100,
    orphan_threshold: int = 2,
) -> SiteArchitectureReport:
    """One-call helper: build graph, run PageRank, produce report."""
    graph = build_link_graph(pages, link_extractions)
    pr = compute_pagerank(graph, damping=pagerank_damping, max_iterations=pagerank_max_iterations)

    for url, node in graph.nodes.items():
        graph.nodes[url] = LinkNode(
            url=node.url,
            depth=node.depth,
            incoming_count=node.incoming_count,
            outgoing_count=node.outgoing_count,
            pagerank=pr.get(url, 0.0),
        )

    orphans = find_orphan_pages(graph)
    dead_ends = find_dead_end_pages(graph)
    thin = identify_thin_pages(graph, threshold=orphan_threshold)
    depths = [n.depth for n in graph.nodes.values()]
    pr_sorted = sorted(graph.nodes.keys(), key=lambda u: graph.nodes[u].pagerank, reverse=True)

    internal_edges = [e for e in graph.edges if e.link_type == "internal"]
    total_pages = len(graph.nodes)

    depth_dist: dict[int, int] = dict(Counter(depths))
    velocity = compute_link_velocity(graph)

    # Calculate Internal Graph PageRank Gini coefficient
    pr_values = tuple(graph.nodes[u].pagerank for u in graph.nodes)
    gini = compute_gini(pr_values)

    return SiteArchitectureReport(
        total_pages=total_pages,
        total_internal_links=len(internal_edges),
        avg_links_per_page=round(len(internal_edges) / total_pages, 2) if total_pages else 0,
        orphans=orphans,
        dead_ends=dead_ends,
        max_depth=max(depths) if depths else 0,
        avg_depth=round(sum(depths) / len(depths), 2) if depths else 0,
        depth_distribution=depth_dist,
        pagerank_top_10=tuple(pr_sorted[:10]),
        pagerank_bottom_10=tuple(pr_sorted[-10:]),
        thin_connection_pages=thin,
        link_velocity=velocity,
        pagerank_gini=gini,
        pagerank_values=tuple(round(v, 6) for v in sorted(pr_values, reverse=True)),
    )
