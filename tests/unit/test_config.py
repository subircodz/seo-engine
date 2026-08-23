"""Settings loading and precedence."""

from sie.config import CrawlerSettings, Settings


def test_defaults_are_safe() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.database_url.startswith("sqlite+aiosqlite://")
    assert settings.crawler.respect_robots_txt is True
    assert settings.crawler.max_concurrent_requests >= 1
    assert settings.is_production is False


def test_environment_variables_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("SIE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SIE_PORT", "9999")
    monkeypatch.setenv("SIE_CRAWLER__MAX_PAGES", "42")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"
    assert settings.port == 9999
    assert settings.crawler.max_pages == 42


def test_crawler_politeness_defaults_are_sane() -> None:
    crawler = CrawlerSettings()

    assert crawler.rate_limit_per_host > 0
    assert crawler.request_timeout_seconds > 0
    assert crawler.respect_robots_txt is True
    assert crawler.follow_cross_origin is False
    assert crawler.max_retries >= 0
