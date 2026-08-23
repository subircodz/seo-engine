"""System diagnostics endpoints."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    database_ok = await request.app.state.database.healthcheck()
    return {
        "status": "ok" if database_ok else "degraded",
        "app": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "database": "ok" if database_ok else "unreachable",
    }
