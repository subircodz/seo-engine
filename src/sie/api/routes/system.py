"""System diagnostics endpoints."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    database_ok = await request.app.state.database.healthcheck()
    sp = settings.search_provider
    provider_info: dict[str, object] = {
        "enabled": sp.enabled,
        "provider_name": sp.provider_name if sp.enabled else "mock",
        "base_url": sp.base_url if sp.enabled and sp.base_url else None,
        "has_api_key": bool(sp.api_key) if sp.enabled else False,
    }
    return {
        "status": "ok" if database_ok else "degraded",
        "app_name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "debug": settings.debug,
        "database": "ok" if database_ok else "unreachable",
        "search_provider": provider_info,
    }
