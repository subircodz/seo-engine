"""Server-rendered HTML routes (Jinja2 + HTMX-ready)."""

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from sie.api.templates import templates
from sie.config import get_settings

router = APIRouter(tags=["web"])


class _DefaultSettings:
    """Fallback for test contexts where lifespan hasn't run."""

    app_name: str = "SEO Intelligence Engine"
    version: str = "dev"
    environment: str = "development"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///./sie.db"


def _ctx(request: Request, **extra: object) -> dict[str, object]:
    settings = getattr(request.app.state, "settings", None) or _DefaultSettings()
    ctx: dict[str, object] = {"settings": settings}
    ctx.update(extra)
    return ctx


def _get_base_url(request: Request) -> str:
    """Get the base URL for the site."""
    return str(request.base_url).rstrip("/")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt(request: Request) -> PlainTextResponse:
    """Serve robots.txt for search engine crawlers."""
    base_url = _get_base_url(request)
    sitemap_url = f"{base_url}/sitemap.xml"
    
    content = f"""# SEO Intelligence Engine - robots.txt
User-agent: *
Allow: /

# Sitemap
Sitemap: {sitemap_url}

# Crawl-delay for polite crawling
Crawl-delay: 10

# Disallow admin/api paths
Disallow: /api/
Disallow: /docs
Disallow: /health
Disallow: /_internal/
"""
    return PlainTextResponse(content=content, media_type="text/plain")


@router.get("/sitemap.xml", response_class=Response)
async def sitemap_xml(request: Request) -> Response:
    """Generate dynamic sitemap.xml for search engines."""
    base_url = _get_base_url(request)
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    
    # Static pages
    urls = [
        {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/site", "changefreq": "weekly", "priority": "0.9"},
        {"loc": f"{base_url}/search", "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{base_url}/datasets", "changefreq": "daily", "priority": "0.8"},
        {"loc": f"{base_url}/intelligence", "changefreq": "weekly", "priority": "0.7"},
        {"loc": f"{base_url}/industry", "changefreq": "weekly", "priority": "0.6"},
        {"loc": f"{base_url}/reports", "changefreq": "monthly", "priority": "0.5"},
    ]
    
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    
    for url in urls:
        xml_parts.append("  <url>")
        xml_parts.append(f"    <loc>{url['loc']}</loc>")
        xml_parts.append(f"    <lastmod>{now}</lastmod>")
        xml_parts.append(f"    <changefreq>{url['changefreq']}</changefreq>")
        xml_parts.append(f"    <priority>{url['priority']}</priority>")
        xml_parts.append("  </url>")
    
    xml_parts.append("</urlset>")
    
    return Response(
        content="\n".join(xml_parts),
        media_type="application/xml",
    )


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_ctx(request, active_page="dashboard"),
    )


@router.get("/datasets", response_class=HTMLResponse)
async def datasets_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="datasets.html",
        context=_ctx(request, active_page="datasets"),
    )


@router.get("/datasets/{dataset_id}", response_class=HTMLResponse)
async def dataset_detail_page(dataset_id: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dataset_detail.html",
        context=_ctx(request, active_page="datasets", dataset_id=dataset_id),
    )


@router.get("/intelligence", response_class=HTMLResponse)
async def intelligence_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="intelligence.html",
        context=_ctx(request, active_page="intelligence"),
    )


@router.get("/industry", response_class=HTMLResponse)
async def industry_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="industry.html",
        context=_ctx(request, active_page="industry"),
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context=_ctx(request, active_page="search"),
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context=_ctx(request, active_page="reports"),
    )


@router.get("/site", response_class=HTMLResponse)
async def site_analysis_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="site_analysis.html",
        context=_ctx(request, active_page="site"),
    )
