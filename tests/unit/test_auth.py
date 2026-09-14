from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from sie.api.auth import api_key_auth, optional_api_key_auth, verify_api_key
from sie.config import APISettings


def _request(settings: APISettings, headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],  # noqa: E501
        "app": SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(api=settings))),
    }
    return Request(scope)


def test_verify_api_key_uses_constant_time_comparison():
    assert verify_api_key("secret", ["other", "secret"]) is True
    assert verify_api_key("wrong", ["secret"]) is False
    assert verify_api_key("secret", []) is False


@pytest.mark.asyncio
async def test_required_auth_honors_custom_header():
    settings = APISettings(enabled=True, api_keys=["secret"], header_name="X-Internal-Key")
    request = _request(settings, {"X-Internal-Key": "secret"})

    assert await api_key_auth(request) == "secret"


@pytest.mark.asyncio
async def test_required_auth_rejects_default_header_when_custom_header_configured():
    settings = APISettings(enabled=True, api_keys=["secret"], header_name="X-Internal-Key")
    request = _request(settings, {"X-API-Key": "secret"})

    with pytest.raises(HTTPException) as exc_info:
        await api_key_auth(request)

    assert exc_info.value.status_code == 401
    assert "X-Internal-Key" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_optional_auth_honors_custom_header():
    settings = APISettings(enabled=True, api_keys=["secret"], header_name="X-Internal-Key")
    valid_request = _request(settings, {"X-Internal-Key": "secret"})
    invalid_request = _request(settings, {"X-API-Key": "secret"})

    assert await optional_api_key_auth(valid_request) == "secret"
    assert await optional_api_key_auth(invalid_request) is None
