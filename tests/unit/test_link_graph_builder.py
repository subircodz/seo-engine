"""Link graph engine unit tests."""

import pytest

from sie.domain.engines.link_graph import (
    build_architecture_report,
    build_link_graph,
    compute_link_velocity,
    compute_pagerank,
    find_dead_end_pages,
    find_depth_outliers,
    find_orphan_pages,
    identify_thin_pages,
)
from sie.domain.models.audit import ExtractedLink, LinkExtraction, LinkGraph
from sie.domain.models.page import FetchedPage


def _page(url, depth=0):
    return FetchedPage(
        url=url,
        final_url=url,
        status_code=200,
        headers={},
        content=b"<html></html>",
        content_type="text/html",
        depth=depth,
    )


def _extraction(source_url, links):
    return LinkExtraction(source_url=source_url, links=tuple(links))


def _link(target, anchor="", is_internal=True, rel=frozenset()):
    return ExtractedLink(target_url=target, anchor_text=anchor, is_internal=is_internal, rel=rel)


# ── Graph construction ────────────────────────────────────────────────────


def test_build_graph_basic():
    pages = [_page("https://a.com/"), _page("https://a.com/about")]
    extractions = {
        "https://a.com/": _extraction("https://a.com/", [_link("https://a.com/about")]),
        "https://a.com/about": _extraction("https://a.com/about", [_link("https://a.com/")]),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 2
    assert graph.nodes["https://a.com/"].outgoing_count == 1
    assert graph.nodes["https://a.com/about"].incoming_count == 1


def test_build_graph_external_links_not_counted_as_incoming():
    pages = [_page("https://a.com/")]
    extractions = {
        "https://a.com/": _extraction(
            "https://a.com/",
            [_link("https://b.com/other", is_internal=False)],
        ),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    assert len(graph.edges) == 1
    assert graph.edges[0].link_type == "external"
    assert graph.nodes["https://a.com/"].outgoing_count == 1
    # External target not in nodes, so no incoming for it
    assert all(n.incoming_count == 0 for n in graph.nodes.values())


def test_build_graph_nofollow_edge_type():
    pages = [_page("https://a.com/")]
    extractions = {
        "https://a.com/": _extraction(
            "https://a.com/", [_link("https://a.com/page", rel=frozenset({"nofollow"}))]
        ),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    assert graph.edges[0].link_type == "nofollow"


# ── PageRank ──────────────────────────────────────────────────────────────


def test_pagerank_basic():
    pages = [
        _page("https://a.com/"),
        _page("https://a.com/a"),
        _page("https://a.com/b"),
    ]
    # Hub → A, Hub → B, A → Hub, B → Hub
    extractions = {
        "https://a.com/": _extraction(
            "https://a.com/",
            [_link("https://a.com/a"), _link("https://a.com/b")],
        ),
        "https://a.com/a": _extraction("https://a.com/a", [_link("https://a.com/")]),
        "https://a.com/b": _extraction("https://a.com/b", [_link("https://a.com/")]),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    pr = compute_pagerank(graph)
    assert len(pr) == 3
    assert sum(pr.values()) == pytest.approx(1.0, abs=0.01)
    # Hub should have highest PageRank
    assert pr["https://a.com/"] > pr["https://a.com/a"]
    assert pr["https://a.com/"] > pr["https://a.com/b"]


def test_pagerank_empty_graph():
    graph = LinkGraph(nodes={}, edges=())
    pr = compute_pagerank(graph)
    assert pr == {}


def test_pagerank_dangling_nodes():
    """Dangling nodes should redistribute their PR uniformly."""
    pages = [_page("https://a.com/"), _page("https://a.com/leaf")]
    extractions = {
        "https://a.com/": _extraction("https://a.com/", [_link("https://a.com/leaf")]),
        "https://a.com/leaf": _extraction("https://a.com/leaf", []),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    pr = compute_pagerank(graph)
    assert sum(pr.values()) == pytest.approx(1.0, abs=0.01)
    # Leaf has no outgoing, so it's a dangling node — should still get PR
    assert pr["https://a.com/leaf"] > 0


# ── Orphan / dead-end detection ───────────────────────────────────────────


def test_orphan_detection():
    pages = [_page("https://a.com/"), _page("https://a.com/orphan")]
    extractions = {
        "https://a.com/": _extraction("https://a.com/", []),
        "https://a.com/orphan": _extraction("https://a.com/orphan", []),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    orphans = find_orphan_pages(graph)
    # Root gets 0 incoming since no links point to it
    # Orphan page gets 0 incoming too
    assert len(orphans) == 2
    assert "https://a.com/orphan" in orphans


def test_dead_end_detection():
    pages = [_page("https://a.com/"), _page("https://a.com/dead")]
    extractions = {
        "https://a.com/": _extraction("https://a.com/", [_link("https://a.com/dead")]),
        "https://a.com/dead": _extraction("https://a.com/dead", []),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    dead_ends = find_dead_end_pages(graph)
    assert "https://a.com/dead" in dead_ends
    assert "https://a.com/" not in dead_ends


# ── Depth outliers ────────────────────────────────────────────────────────


def test_depth_outliers():
    pages = [_page("https://a.com/", depth=0), _page("https://a.com/d1/d2/d3/d4/d5/d6", depth=6)]
    extractions = {}
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    outliers = find_depth_outliers(graph, max_depth=5)
    assert "https://a.com/d1/d2/d3/d4/d5/d6" in outliers
    assert "https://a.com/" not in outliers


# ── Thin pages ────────────────────────────────────────────────────────────


def test_thin_page_identification():
    pages = [_page("https://a.com/"), _page("https://a.com/thin")]
    extractions = {
        "https://a.com/": _extraction("https://a.com/", []),
        "https://a.com/thin": _extraction("https://a.com/thin", []),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    thin = identify_thin_pages(graph, threshold=2)
    # Both have incoming+outgoing <= 2
    assert "https://a.com/thin" in thin


# ── Link velocity ─────────────────────────────────────────────────────────


def test_link_velocity():
    pages = [_page("https://a.com/"), _page("https://a.com/blog/post1")]
    extractions = {
        "https://a.com/": _extraction("https://a.com/", [_link("https://a.com/blog/post1")]),
        "https://a.com/blog/post1": _extraction("https://a.com/blog/post1", []),
    }
    graph = build_link_graph(pages, extractions, base_domain="a.com")
    velocity = compute_link_velocity(graph)
    assert velocity.avg_internal_links_per_page == 0.5  # 1 link / 2 pages
    # Root section is "/" for the homepage
    assert velocity.links_by_section.get("blog") == 1 or velocity.links_by_section.get("/") == 1


# ── Full architecture report ──────────────────────────────────────────────


def test_build_architecture_report():
    pages = [_page("https://a.com/"), _page("https://a.com/about"), _page("https://a.com/contact")]
    extractions = {
        "https://a.com/": _extraction(
            "https://a.com/",
            [_link("https://a.com/about"), _link("https://a.com/contact")],
        ),
        "https://a.com/about": _extraction("https://a.com/about", [_link("https://a.com/")]),
        "https://a.com/contact": _extraction("https://a.com/contact", []),
    }
    report = build_architecture_report(pages, extractions)
    assert report.total_pages == 3
    assert report.total_internal_links == 3
    assert report.max_depth == 0
    assert len(report.pagerank_top_10) == 3
    assert isinstance(report.link_velocity.avg_internal_links_per_page, float)
