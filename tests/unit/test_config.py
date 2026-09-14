"""Settings loading and precedence."""

import pytest
from pydantic import ValidationError

from sie.config import CrawlerSettings, SearchProviderSettings, Settings


def test_defaults_are_safe() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.database_url.startswith("sqlite+aiosqlite://")
    assert settings.crawler.respect_robots_txt is True
    assert settings.crawler.max_concurrent_requests >= 1
    assert settings.crawler.max_redirects >= 0
    assert settings.crawler.max_response_bytes > 0
    assert settings.is_production is False


def test_environment_variables_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("SIE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SIE_PORT", "9999")
    monkeypatch.setenv("SIE_CRAWLER__MAX_PAGES", "42")
    monkeypatch.setenv("SIE_CRAWLER__MAX_REDIRECTS", "3")
    monkeypatch.setenv("SIE_CRAWLER__MAX_RESPONSE_BYTES", "2048")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"
    assert settings.port == 9999
    assert settings.crawler.max_pages == 42
    assert settings.crawler.max_redirects == 3
    assert settings.crawler.max_response_bytes == 2048


def test_crawler_politeness_defaults_are_sane() -> None:
    crawler = CrawlerSettings()

    assert crawler.rate_limit_per_host > 0
    assert crawler.request_timeout_seconds > 0
    assert crawler.respect_robots_txt is True
    assert crawler.follow_cross_origin is False
    assert crawler.max_retries >= 0
    assert crawler.max_redirects >= 0
    assert crawler.max_response_bytes > 0


def test_crawler_limits_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        CrawlerSettings(max_redirects=-1)
    with pytest.raises(ValidationError):
        CrawlerSettings(max_response_bytes=0)


# ════════════════════════════════════════════════════════════════════════════
# SearchProviderSettings
# ════════════════════════════════════════════════════════════════════════════


class TestSearchProviderSettings:
    def test_defaults(self) -> None:
        sp = SearchProviderSettings()

        assert sp.enabled is False
        assert sp.provider_name == "mock"
        assert sp.base_url == ""
        assert sp.api_key == ""
        assert sp.timeout_seconds == 30.0

    def test_enabled_flag(self) -> None:
        sp = SearchProviderSettings(enabled=True)
        assert sp.enabled is True

    def test_provider_name(self) -> None:
        sp = SearchProviderSettings(provider_name="serpapi")
        assert sp.provider_name == "serpapi"

    def test_base_url(self) -> None:
        sp = SearchProviderSettings(base_url="https://api.example.com")
        assert sp.base_url == "https://api.example.com"

    def test_optional_api_key_is_empty_string(self) -> None:
        sp = SearchProviderSettings()
        assert sp.api_key == ""

    def test_api_key_can_be_set(self) -> None:
        sp = SearchProviderSettings(api_key="sk-test-key")
        assert sp.api_key == "sk-test-key"

    def test_timeout_positive(self) -> None:
        sp = SearchProviderSettings(timeout_seconds=10.0)
        assert sp.timeout_seconds == 10.0

    def test_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SearchProviderSettings(timeout_seconds=0)

    def test_timeout_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            SearchProviderSettings(timeout_seconds=-1.0)


class TestSearchProviderSettingsOnRoot:
    def test_settings_has_search_provider(self) -> None:
        settings = Settings(_env_file=None)
        assert hasattr(settings, "search_provider")
        assert isinstance(settings.search_provider, SearchProviderSettings)

    def test_search_provider_disabled_by_default(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.search_provider.enabled is False

    def test_env_override_search_provider_enabled(self, monkeypatch) -> None:
        monkeypatch.setenv("SIE_SEARCH_PROVIDER__ENABLED", "true")
        settings = Settings(_env_file=None)
        assert settings.search_provider.enabled is True

    def test_env_override_search_provider_name(self, monkeypatch) -> None:
        monkeypatch.setenv("SIE_SEARCH_PROVIDER__PROVIDER_NAME", "dataforseo")
        settings = Settings(_env_file=None)
        assert settings.search_provider.provider_name == "dataforseo"

    def test_env_override_search_provider_base_url(self, monkeypatch) -> None:
        monkeypatch.setenv("SIE_SEARCH_PROVIDER__BASE_URL", "https://api.dataforseo.com")
        settings = Settings(_env_file=None)
        assert settings.search_provider.base_url == "https://api.dataforseo.com"

    def test_env_override_search_provider_timeout(self, monkeypatch) -> None:
        monkeypatch.setenv("SIE_SEARCH_PROVIDER__TIMEOUT_SECONDS", "15.5")
        settings = Settings(_env_file=None)
        assert settings.search_provider.timeout_seconds == 15.5


class TestSearchProviderApiKeyNotExposed:
    def test_api_key_not_in_repr(self) -> None:
        """API key must not leak through default repr."""
        sp = SearchProviderSettings(api_key="super-secret-key-12345")
        r = repr(sp)
        assert "super-secret-key-12345" not in r

    def test_api_key_not_in_str(self) -> None:
        """API key must not leak through str()."""
        sp = SearchProviderSettings(api_key="super-secret-key-12345")
        s = str(sp)
        assert "super-secret-key-12345" not in s


def test_nested_database_auto_migrate_env_override(monkeypatch) -> None:
    """The documented nested environment variable must control migration policy."""
    monkeypatch.setenv("SIE_DATABASE__AUTO_MIGRATE", "false")

    settings = Settings(_env_file=None)

    assert settings.database.auto_migrate is False
    assert settings.auto_migrate is False


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError, match="SIE_DEBUG must be false"):
        Settings(_env_file=None, environment="production", debug=True, host="0.0.0.0")


def test_production_rejects_auto_migrate() -> None:
    with pytest.raises(ValidationError, match="SIE_DATABASE__AUTO_MIGRATE"):
        Settings(_env_file=None, environment="production", debug=False, host="0.0.0.0")


def test_production_rejects_loopback_host() -> None:
    with pytest.raises(ValidationError, match="SIE_HOST"):
        Settings(
            _env_file=None,
            environment="production",
            debug=False,
            host="127.0.0.1",
            database={"auto_migrate": False},
        )


def test_production_requires_api_key_when_auth_enabled() -> None:
    with pytest.raises(ValidationError, match="SIE_API__API_KEYS"):
        Settings(
            _env_file=None,
            environment="production",
            debug=False,
            host="0.0.0.0",
            database={"auto_migrate": False},
            api={"enabled": True},
        )


def test_production_configuration_is_accepted() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        host="0.0.0.0",
        database={"auto_migrate": False},
        api={"enabled": True, "api_keys": ["test-key"]},
    )

    assert settings.is_production is True
    assert settings.auto_migrate is False


def test_database_url_not_in_root_repr() -> None:
    database_url = "postgresql+asyncpg://user:secret@db/sie"
    settings = Settings(_env_file=None, database_url=database_url)

    assert database_url not in repr(settings)
