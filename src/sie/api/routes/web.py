"""Server-rendered HTML routes (Jinja2 + HTMX-ready)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from sie.api.templates import templates

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
