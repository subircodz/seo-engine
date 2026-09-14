"""API authentication behavior."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from sie.api.auth import api_key_auth, verify_api_key
from sie.config import APISettings


def _request(api_settings: APISettings, headers: dict[str, str] | None = None):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(api=api_settings))),
        headers=headers or {},
    )


def test_verify_api_key_uses_exact_match() -> None:
    assert verify_api_key("secret", ["secret"]) is True
    assert verify_api_key("wrong", ["secret"]) is False
    assert verify_api_key("secret", []) is False


@pytest.mark.asyncio
async def test_disabled_auth_allows_request() -> None:
    result = await api_key_auth(_request(APISettings(enabled=False)))
    assert result == "dev-mode"


@pytest.mark.asyncio
async def test_custom_header_is_honored() -> None:
    settings = APISettings(enabled=True, api_keys=["secret"], header_name="X-Internal-Key")
    request = _request(settings, {"X-Internal-Key": "secret"})
    assert await api_key_auth(request) == "secret"


@pytest.mark.asyncio
async def test_missing_custom_header_is_rejected() -> None:
    settings = APISettings(enabled=True, api_keys=["secret"], header_name="X-Internal-Key")
    with pytest.raises(HTTPException) as exc_info:
        await api_key_auth(_request(settings))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_custom_header_value_is_rejected() -> None:
    settings = APISettings(enabled=True, api_keys=["secret"], header_name="X-Internal-Key")
    with pytest.raises(HTTPException) as exc_info:
        await api_key_auth(_request(settings, {"X-Internal-Key": "wrong"}))
    assert exc_info.value.status_code == 401
