"""System health and diagnostics endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["system"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Return success when the application process is alive."""

    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Return success only when required runtime dependencies are reachable."""

    database_ok = await request.app.state.database.healthcheck()
    if not database_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unreachable"},
        )
    return JSONResponse(status_code=200, content={"status": "ready", "database": "ok"})


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Return a minimal operational health summary without exposing configuration."""

    settings = request.app.state.settings
    database_ok = await request.app.state.database.healthcheck()
    return {
        "status": "ok" if database_ok else "degraded",
        "app_name": settings.app_name,
        "version": settings.version,
        "database": "ok" if database_ok else "unreachable",
    }
