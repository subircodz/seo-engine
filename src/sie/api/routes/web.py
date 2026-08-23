"""Server-rendered HTML routes (Jinja2 + HTMX-ready)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from sie.api.templates import templates

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"settings": request.app.state.settings},
    )
