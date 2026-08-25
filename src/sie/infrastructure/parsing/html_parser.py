"""HTML parser: FetchedPage → PageDOM + LinkExtraction.

This is the *only* module that imports BeautifulSoup.  Everything downstream
(audit engines, link-graph engine) works on the pure domain models produced
here.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from sie.domain.models.audit import (
    ExtractedLink,
    LinkExtraction,
    PageDOM,
    PageImage,
)
from sie.domain.models.page import FetchedPage

_SKIP_HREF_PREFIXES = ("#", "javascript:", "mailto:", "tel:", "data:")


def _soup(html: str) -> BeautifulSoup | None:
    if not html.strip():
        return None
    return BeautifulSoup(html, "html.parser")


def parse_page(page: FetchedPage) -> PageDOM:
    """Extract SEO-relevant structure from a fetched page."""
    html = page.decoded_text() if page.is_html else ""
    soup = _soup(html)
    is_https = page.url.startswith("https://")

    title = soup.title.string.strip() if soup and soup.title and soup.title.string else None

    def _meta_content(name: str) -> str | None:
        tag = soup.find("meta", attrs={"name": name}) if soup else None
        content = tag.get("content") if tag else None
        return content.strip() if content else None

    meta_description = _meta_content("description")
    meta_robots = _meta_content("robots")

    canonicals: tuple[str, ...] = ()
    if soup:
        canonicals = tuple(
            tag["href"]
            for tag in soup.find_all("link", attrs={"rel": "canonical"})
            if tag.get("href")
        )
    canonical = canonicals[0] if canonicals else None

    h1s = tuple(t.get_text(strip=True) for t in (soup.find_all("h1") if soup else []))
    h2s = tuple(t.get_text(strip=True) for t in (soup.find_all("h2") if soup else []))
    h3s = tuple(t.get_text(strip=True) for t in (soup.find_all("h3") if soup else []))

    hreflangs: tuple[tuple[str, str], ...] = ()
    if soup:
        hreflangs = tuple(
            (t["hreflang"], t.get("href", ""))
            for t in soup.find_all("link", attrs={"rel": "alternate", "hreflang": True})
        )

    jsonld_types: list[str] = []
    if soup:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    t = item.get("@type")
                    if isinstance(t, str):
                        jsonld_types.append(t)
                    elif isinstance(t, list):
                        jsonld_types.extend(x for x in t if isinstance(x, str))

    images: tuple[PageImage, ...] = ()
    internal_links: list[str] = []
    external_links: list[str] = []
    nofollow_links: list[str] = []
    mixed_content = False

    if soup:
        images = tuple(
            PageImage(src=img.get("src", ""), alt=img.get("alt", ""))
            for img in soup.find_all("img")
        )
        base_domain = (urlsplit(page.url).hostname or "").lower()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(_SKIP_HREF_PREFIXES):
                continue
            resolved = urljoin(page.url, href)
            target_domain = (urlsplit(resolved).hostname or "").lower()
            rel_raw = a.get("rel", [])
            rel = frozenset(rel_raw) if isinstance(rel_raw, list) else frozenset([str(rel_raw)])
            if "nofollow" in rel:
                nofollow_links.append(resolved)
            if target_domain == base_domain:
                internal_links.append(resolved)
            elif target_domain:
                external_links.append(resolved)

        if is_https:
            for tag in soup.find_all(["img", "script", "link", "iframe"]):
                src = tag.get("src") or tag.get("href") or ""
                if src.startswith("http://"):
                    mixed_content = True
                    break

    query_param_count = len(parse_query_keys(page.url))

    return PageDOM(
        url=page.url,
        status_code=page.status_code,
        content_type=page.content_type,
        html_size=len(page.content),
        title=title,
        meta_description=meta_description,
        meta_robots=meta_robots,
        canonical=canonical,
        canonicals=canonicals,
        h1s=h1s,
        h2s=h2s,
        h3s=h3s,
        hreflangs=hreflangs,
        jsonld_types=tuple(jsonld_types),
        images=images,
        internal_links=tuple(internal_links),
        external_links=tuple(external_links),
        nofollow_links=tuple(nofollow_links),
        mixed_content=mixed_content,
        query_param_count=query_param_count,
    )


def extract_links(page: FetchedPage) -> LinkExtraction:
    """Extract outgoing links with anchor text + rel info."""
    dom = parse_page(page)
    soup = _soup(page.decoded_text() if page.is_html else "")
    links: list[ExtractedLink] = []
    if soup:
        base_domain = (urlsplit(page.url).hostname or "").lower()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(_SKIP_HREF_PREFIXES):
                continue
            resolved = urljoin(page.url, href)
            target_domain = (urlsplit(resolved).hostname or "").lower()
            rel_raw = a.get("rel", [])
            rel = frozenset(rel_raw) if isinstance(rel_raw, list) else frozenset([str(rel_raw)])
            links.append(
                ExtractedLink(
                    target_url=resolved,
                    anchor_text=a.get_text(strip=True)[:200],
                    is_internal=(target_domain == base_domain),
                    rel=rel,
                )
            )
    return LinkExtraction(source_url=dom.url, links=tuple(links))


def parse_query_keys(url: str) -> list[str]:
    query = urlsplit(url).query
    if not query:
        return []
    return [k for k in parse_qs(query)]


class Bs4PageParser:
    """BeautifulSoup-backed implementation of the PageParser port."""

    def parse_page(self, page: FetchedPage) -> PageDOM:
        return parse_page(page)

    def parse_links(self, page: FetchedPage) -> LinkExtraction:
        return extract_links(page)
