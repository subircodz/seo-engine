"""Tests for application-level request correlation and security headers."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sie.api.app import RequestIdMiddleware, SecurityHeadersMiddleware


def _build_app(*, production: bool) -> FastAPI:
    app = FastAPI()
    app.state.settings = SimpleNamespace(is_production=production)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def test_request_id_is_preserved_when_valid():
    with TestClient(_build_app(production=False)) as client:
        response = client.get("/health", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"


def test_request_id_is_replaced_when_too_long():
    with TestClient(_build_app(production=False)) as client:
        response = client.get("/health", headers={"X-Request-ID": "x" * 129})

    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 200
    assert len(request_id) <= 128
    assert request_id != "x" * 129


def test_security_headers_are_applied_in_production():
    with TestClient(_build_app(production=True)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    assert "server" not in response.headers


def test_hsts_is_not_applied_outside_production():
    with TestClient(_build_app(production=False)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert "strict-transport-security" not in response.headers
