"""API-key authentication behavior and startup-safe settings resolution."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from sie.api.auth import api_key_auth, optional_api_key_auth, verify_api_key
from sie.config import APISettings


def _request(api_settings: APISettings | None, headers: dict[str, str] | None = None):
    state = SimpleNamespace()
    if api_settings is not None:
        state.settings = SimpleNamespace(api=api_settings)
    return SimpleNamespace(
        app=SimpleNamespace(state=state),
        headers=headers or {},
    )


def test_verify_api_key_uses_exact_constant_time_match() -> None:
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
    assert exc_info.value.headers == {"WWW-Authenticate": "ApiKey"}


@pytest.mark.asyncio
async def test_wrong_custom_header_value_is_rejected() -> None:
    settings = APISettings(enabled=True, api_keys=["secret"], header_name="X-Internal-Key")

    with pytest.raises(HTTPException) as exc_info:
        await api_key_auth(_request(settings, {"X-Internal-Key": "wrong"}))

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_optional_auth_accepts_valid_key_without_requiring_it() -> None:
    settings = APISettings(enabled=True, api_keys=["secret"])

    assert await optional_api_key_auth(_request(settings)) is None
    assert await optional_api_key_auth(_request(settings, {"X-API-Key": "secret"})) == "secret"
    assert await optional_api_key_auth(_request(settings, {"X-API-Key": "wrong"})) is None


@pytest.mark.asyncio
async def test_auth_falls_back_to_config_when_lifespan_has_not_started(monkeypatch) -> None:
    fallback_settings = SimpleNamespace(
        api=APISettings(enabled=True, api_keys=["secret"], header_name="X-Internal-Key")
    )
    monkeypatch.setattr("sie.api.auth.get_settings", lambda: fallback_settings)

    request = _request(None, {"X-Internal-Key": "secret"})

    assert await api_key_auth(request) == "secret"
