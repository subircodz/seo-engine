"""URL normalization, scope checks, and link extraction helpers."""

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

_DEFAULT_PORTS = {"http": 80, "https": 443}


def _safe_port(parts: urlsplit) -> int | None:
    try:
        return parts.port
    except ValueError:
        return None


def normalize_url(raw: str) -> str:
    """Canonical form for dedup/scope decisions.

    Lowercases scheme/host, strips fragments and default ports, maps the empty
    path to ``/`` and sorts query parameters. Credentials in the netloc are
    dropped. Non-HTTP(S) input is returned structurally normalized as-is.
    """
    parts = urlsplit(raw.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = _safe_port(parts)
    if port is not None and _DEFAULT_PORTS.get(scheme) == port:
        port = None
    netloc = host if port is None else f"{host}:{port}"
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, parts.path or "/", query, ""))


def is_crawlable(url: str) -> bool:
    """True when the URL has an HTTP(S) scheme and a host."""
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def same_site(url_a: str, url_b: str) -> bool:
    """Host equality ignoring a leading ``www.`` on either side."""

    def registrable(host: str) -> str:
        return host[4:] if host.startswith("www.") else host

    return registrable(host_of(url_a)) == registrable(host_of(url_b))


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract and normalize every anchor href, deduplicated, order preserved."""
    soup = BeautifulSoup(html, "lxml")
    base_tag = soup.find("base", href=True)
    resolved_base = urljoin(base_url, base_tag["href"]) if base_tag is not None else base_url
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        candidate = normalize_url(urljoin(resolved_base, anchor["href"].strip()))
        if candidate not in seen:
            seen.add(candidate)
            links.append(candidate)
    return links
