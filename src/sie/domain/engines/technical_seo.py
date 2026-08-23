"""Technical SEO audit rules engine (pure functions, no I/O).

Every rule implements :class:`~sie.domain.models.audit.AuditRule` — a frozen
dataclass with a ``check`` method that returns an :class:`AuditFinding` or
``None``.  Rules are grouped by priority (P0 / P1 / P2) and filtered at
runtime by the audit service.
"""

from __future__ import annotations

from collections import Counter
from urllib.parse import parse_qs, urlsplit

from sie.domain.models.audit import (
    AuditContext,
    AuditFinding,
    PageDOM,
    TechnicalAuditResult,
)

# ════════════════════════════════════════════════════════════════════════════
# P0 — Critical (ranking-blocking)
# ════════════════════════════════════════════════════════════════════════════


class TitleMissingRule:
    code = "TITLE_MISSING"
    severity = "critical"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.title is None:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Missing <title> tag",
                recommendation="Add a unique, descriptive title (30-60 characters).",
                affected_elements=("<title>",),
            )
        return None


class TitleEmptyRule:
    code = "TITLE_EMPTY"
    severity = "critical"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.title is not None and page.title.strip() == "":
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Empty <title> tag",
                recommendation="Replace with a meaningful title.",
                affected_elements=("<title>",),
            )
        return None


class TitleTooLongRule:
    code = "TITLE_TOO_LONG"
    severity = "critical"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.title is not None and len(page.title) > 60:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Title too long ({len(page.title)} chars, max 60)",
                recommendation="Shorten the title to 60 characters or fewer.",
                affected_elements=("<title>",),
            )
        return None


class TitleDuplicateRule:
    code = "TITLE_DUPLICATE"
    severity = "critical"
    category = "meta"
    needs_context = True

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.title is None or context is None:
            return None
        dupes = [
            u for u, p in context.pages_by_url.items() if p.title == page.title and u != page.url
        ]
        if dupes:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Duplicate title shared with {len(dupes)} other page(s)",
                recommendation="Give each page a unique, descriptive title.",
                affected_elements=("<title>", *dupes[:5]),
            )
        return None


class MetaDescMissingRule:
    code = "META_DESC_MISSING"
    severity = "critical"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.meta_description is None:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Missing meta description",
                recommendation="Add a meta description (120-160 characters).",
                affected_elements=('<meta name="description">',),
            )
        return None


class MetaDescTooLongRule:
    code = "META_DESC_TOO_LONG"
    severity = "critical"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.meta_description is not None and len(page.meta_description) > 160:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Meta description too long ({len(page.meta_description)} chars, max 160)",
                recommendation="Shorten the meta description to 160 characters or fewer.",
                affected_elements=('<meta name="description">',),
            )
        return None


class MetaDescDuplicateRule:
    code = "META_DESC_DUPLICATE"
    severity = "critical"
    category = "meta"
    needs_context = True

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.meta_description is None or context is None:
            return None
        dupes = [
            u
            for u, p in context.pages_by_url.items()
            if p.meta_description == page.meta_description and u != page.url
        ]
        if dupes:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Duplicate meta description shared with {len(dupes)} other page(s)",
                recommendation="Write a unique meta description for each page.",
                affected_elements=('<meta name="description">', *dupes[:5]),
            )
        return None


class CanonicalMissingRule:
    code = "CANONICAL_MISSING"
    severity = "critical"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.canonical is None:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Missing canonical tag",
                recommendation="Add a self-referencing canonical tag.",
                affected_elements=('<link rel="canonical">',),
            )
        return None


class CanonicalSelfRefErrorRule:
    code = "CANONICAL_SELF_REF_ERROR"
    severity = "critical"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.canonical is None:
            return None
        page_path = urlsplit(page.url).path.rstrip("/") or "/"
        canon_path = urlsplit(page.canonical).path.rstrip("/") or "/"
        if page_path != canon_path:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Canonical ({page.canonical}) does not match page URL",
                recommendation="Canonical should be self-referencing (same URL).",
                affected_elements=("<link rel='canonical'>",),
            )
        return None


class CanonicalMultipleRule:
    code = "CANONICAL_MULTIPLE"
    severity = "critical"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if len(page.canonicals) > 1:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Multiple canonical tags found ({len(page.canonicals)})",
                recommendation="Use exactly one canonical tag per page.",
                affected_elements=("<link rel='canonical'>",),
            )
        return None


class H1MissingRule:
    code = "H1_MISSING"
    severity = "critical"
    category = "structure"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if not page.h1s:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Missing <h1> tag",
                recommendation="Add exactly one <h1> that describes the page.",
                affected_elements=("<h1>",),
            )
        return None


class H1EmptyRule:
    code = "H1_EMPTY"
    severity = "critical"
    category = "structure"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if any(h.strip() == "" for h in page.h1s):
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Empty <h1> tag found",
                recommendation="Add meaningful text inside the <h1> tag.",
                affected_elements=("<h1>",),
            )
        return None


class H1MultipleRule:
    code = "H1_MULTIPLE"
    severity = "critical"
    category = "structure"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if len(page.h1s) > 1:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Multiple <h1> tags ({len(page.h1s)})",
                recommendation="Use exactly one <h1> per page.",
                affected_elements=("<h1>",),
            )
        return None


class Status404Rule:
    code = "STATUS_404"
    severity = "critical"
    category = "status"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.status_code == 404:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Page returns 404 Not Found",
                recommendation="Fix the URL, restore the content, or redirect to a valid page.",
            )
        return None


class Status5xxRule:
    code = "STATUS_5XX"
    severity = "critical"
    category = "status"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if 500 <= page.status_code < 600:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Server error ({page.status_code})",
                recommendation="Investigate the server-side issue causing this error.",
            )
        return None


# ════════════════════════════════════════════════════════════════════════════
# P1 — High priority (impacts ranking)
# ════════════════════════════════════════════════════════════════════════════


class MetaRobotsNoindexRule:
    code = "META_ROBOTS_NOINDEX"
    severity = "warning"
    category = "meta"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.meta_robots and "noindex" in page.meta_robots.lower():
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Page is marked noindex",
                recommendation="Remove noindex unless excluded from search.",
                affected_elements=('<meta name="robots">',),
            )
        return None


class HreflangMissingRule:
    code = "HREFLANG_MISSING"
    severity = "warning"
    category = "meta"
    needs_context = True

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if context is None:
            return None
        any_hreflang = any(p.hreflangs for p in context.pages_by_url.values())
        if any_hreflang and not page.hreflangs:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Missing hreflang tag (other pages on this site use hreflang)",
                recommendation="Add hreflang annotations to indicate language/region variants.",
                affected_elements=('<link rel="alternate" hreflang="...">',),
            )
        return None


class HreflangMalformedRule:
    code = "HREFLANG_MALFORMED"
    severity = "warning"
    category = "meta"
    needs_context = False

    _VALID_LANG = frozenset({"x-default"})

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        bad: list[str] = []
        for lang, _ in page.hreflangs:
            if lang in self._VALID_LANG:
                continue
            parts = lang.split("-")
            if not (1 <= len(parts) <= 2 and all(p.isalpha() for p in parts)):
                bad.append(lang)
        if bad:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Malformed hreflang values: {', '.join(bad[:3])}",
                recommendation="Use valid BCP 47 language codes (e.g. 'en', 'en-US', 'x-default').",
                affected_elements=tuple(bad[:5]),
            )
        return None


class SslRedirectRule:
    code = "SSL_REDIRECT"
    severity = "warning"
    category = "security"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.url.startswith("http://"):
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Page served over HTTP instead of HTTPS",
                recommendation="Migrate to HTTPS and set up 301 redirects.",
            )
        return None


class MixedContentRule:
    code = "MIXED_CONTENT"
    severity = "warning"
    category = "security"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.mixed_content:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Mixed content detected (HTTP resources on HTTPS page)",
                recommendation="Update all resource URLs to use HTTPS.",
            )
        return None


class LargeHtmlRule:
    code = "LARGE_HTML"
    severity = "warning"
    category = "performance"
    needs_context = False

    _THRESHOLD = 2 * 1024 * 1024  # 2 MB

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.html_size > self._THRESHOLD:
            mb = round(page.html_size / (1024 * 1024), 1)
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"HTML document is {mb} MB (threshold 2 MB)",
                recommendation="Reduce page size by trimming unused code and lazy-loading content.",
            )
        return None


class JsonLdMissingRule:
    code = "JSONLD_MISSING"
    severity = "warning"
    category = "structured_data"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.status_code == 200 and not page.jsonld_types:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="No JSON-LD structured data found",
                recommendation="Add relevant Schema.org structured data via JSON-LD.",
                affected_elements=("application/ld+json",),
            )
        return None


# ════════════════════════════════════════════════════════════════════════════
# P2 — Medium priority (optimisation opportunities)
# ════════════════════════════════════════════════════════════════════════════


class HeadingHierarchySkipRule:
    code = "HEADING_HIERARCHY_SKIP"
    severity = "info"
    category = "structure"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if not page.h1s:
            return None
        prev_level = 1
        skips: list[str] = []
        for _heading in page.h2s:
            level = 2
            if level - prev_level > 1:
                skips.append(f"h{prev_level}→h{level}")
            prev_level = level
        for _heading in page.h3s:
            level = 3
            if level - prev_level > 1:
                skips.append(f"h{prev_level}→h{level}")
            prev_level = level
        if skips:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"Heading level skipped: {', '.join(skips[:3])}",
                recommendation="Use headings in sequential order (h1 → h2 → h3).",
            )
        return None


class ImageAltMissingRule:
    code = "IMAGE_ALT_MISSING"
    severity = "info"
    category = "accessibility"
    needs_context = False

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        missing = [img.src[:80] for img in page.images if not img.alt.strip()]
        if missing:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"{len(missing)} image(s) missing alt text",
                recommendation="Add descriptive alt text to all images.",
                affected_elements=tuple(missing[:5]),
            )
        return None


class InternalLinksTooFewRule:
    code = "INTERNAL_LINKS_TOO_FEW"
    severity = "info"
    category = "links"
    needs_context = False
    _MIN = 5

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        if page.status_code == 200 and len(page.internal_links) < self._MIN:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
message=f"Only {len(page.internal_links)} internal link(s) on this page",
                 recommendation="Add more internal links (minimum 5) to related content.",
            )
        return None


class InternalLinksTooManyRule:
    code = "INTERNAL_LINKS_TOO_MANY"
    severity = "info"
    category = "links"
    needs_context = False
    _MAX = 100

    def check(self, page: PageDOM, context: AuditContext | None) -> AuditFinding | None:
        if len(page.internal_links) > self._MAX:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"{len(page.internal_links)} internal links on this page (maximum 100)",
                recommendation="Reduce the number of internal links; focus on the most important ones.",
            )
        return None


class UrlExcessiveParamsRule:
    code = "URL_EXCESSIVE_PARAMS"
    severity = "info"
    category = "url"
    needs_context = False
    _MAX_PARAMS = 3

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        param_count = max(page.query_param_count, len(parse_qs(urlsplit(page.url).query)))
        if param_count > self._MAX_PARAMS:
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message=f"URL has {param_count} query parameters (max 3 recommended)",
                recommendation="Simplify the URL structure; use path segments instead of parameters.",
            )
        return None


class UrlSessionIdRule:
    code = "URL_SESSION_ID"
    severity = "info"
    category = "url"
    needs_context = False
    _PATTERNS = ("jsessionid", "aspsessionid", "session_id", "sid=", "phpsessid")

    def check(self, page: PageDOM, context: AuditContext | None = None) -> AuditFinding | None:
        lower = page.url.lower()
        if any(p in lower for p in self._PATTERNS):
            return AuditFinding(
                rule_code=self.code,
                page_url=page.url,
                severity=self.severity,
                message="Session ID detected in URL",
                recommendation="Remove session IDs from URLs; use cookies for session tracking.",
            )
        return None


# ════════════════════════════════════════════════════════════════════════════
# Rule registry
# ════════════════════════════════════════════════════════════════════════════

P0_RULES: list = [
    TitleMissingRule(),
    TitleEmptyRule(),
    TitleTooLongRule(),
    TitleDuplicateRule(),
    MetaDescMissingRule(),
    MetaDescTooLongRule(),
    MetaDescDuplicateRule(),
    CanonicalMissingRule(),
    CanonicalSelfRefErrorRule(),
    CanonicalMultipleRule(),
    H1MissingRule(),
    H1EmptyRule(),
    H1MultipleRule(),
    Status404Rule(),
    Status5xxRule(),
]

P1_RULES: list = [
    MetaRobotsNoindexRule(),
    HreflangMissingRule(),
    HreflangMalformedRule(),
    SslRedirectRule(),
    MixedContentRule(),
    LargeHtmlRule(),
    JsonLdMissingRule(),
]

P2_RULES: list = [
    HeadingHierarchySkipRule(),
    ImageAltMissingRule(),
    InternalLinksTooFewRule(),
    InternalLinksTooManyRule(),
    UrlExcessiveParamsRule(),
    UrlSessionIdRule(),
]

ALL_RULES_BY_PRIORITY: dict[str, list] = {"P0": P0_RULES, "P1": P1_RULES, "P2": P2_RULES}


def get_rules(priorities: set[str]) -> list:
    rules: list = []
    for p in ("P0", "P1", "P2"):
        if p in priorities:
            rules.extend(ALL_RULES_BY_PRIORITY[p])
    return rules


# ════════════════════════════════════════════════════════════════════════════
# Engine entry point
# ════════════════════════════════════════════════════════════════════════════


def run_technical_audit(
    pages: list[PageDOM],
    link_extractions: dict | None = None,
    priorities: set[str] | None = None,
) -> TechnicalAuditResult:
    """Run all enabled rules over *pages* and aggregate findings."""
    if priorities is None:
        priorities = {"P0", "P1", "P2"}

    context = AuditContext(
        pages_by_url={p.url: p for p in pages},
        link_extractions=link_extractions or {},
    )

    rules = get_rules(priorities)
    findings: list[AuditFinding] = []
    for page in pages:
        for rule in rules:
            finding = rule.check(page, context if rule.needs_context else None)
            if finding is not None:
                findings.append(finding)

    by_rule: dict[str, int] = Counter(f.rule_code for f in findings)
    by_severity: dict[str, int] = Counter(f.severity for f in findings)

    page_issue_count: Counter[str] = Counter(f.page_url for f in findings)
    top_offending = tuple(u for u, _ in page_issue_count.most_common(10))

    return TechnicalAuditResult(
        total_pages=len(pages),
        total_issues=len(findings),
        critical_count=by_severity.get("critical", 0),
        warning_count=by_severity.get("warning", 0),
        info_count=by_severity.get("info", 0),
        findings=tuple(findings),
        summary_by_rule=dict(by_rule),
        summary_by_severity=dict(by_severity),
        top_offending_pages=top_offending,
    )
