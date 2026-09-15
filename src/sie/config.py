"""Application settings.

All runtime configuration comes from the environment (optionally via a local
``.env`` file). Every variable is prefixed with ``SIE_``; nested models use
``__`` as the delimiter (e.g. ``SIE_CRAWLER__MAX_PAGES``).
"""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from sie import __version__

EnvironmentName = Literal["development", "test", "production"]


class SecretSafeModel(BaseModel):
    """Base model that redacts credential-like fields from string representations."""

    _SECRET_FIELDS = frozenset(
        {
            "api_key",
            "api_keys",
            "access_token",
            "client_secret",
            "refresh_token",
            "password",
            "redis_url",
        }
    )

    def __repr_args__(self):
        for name, value in super().__repr_args__():
            if name in self._SECRET_FIELDS or any(
                token in name.lower() for token in ("secret", "password", "token", "api_key")
            ):
                yield name, "**********"
            else:
                yield name, value


class CrawlerSettings(SecretSafeModel):
    """Politeness and scope defaults consumed by the Crawler Engine."""

    user_agent: str = f"Mozilla/5.0 (compatible; SEOIntelligenceEngine/{__version__})"
    connect_timeout_seconds: float = Field(default=5.0, gt=0)
    read_timeout_seconds: float = Field(default=20.0, gt=0)
    write_timeout_seconds: float = Field(default=10.0, gt=0)
    pool_timeout_seconds: float = Field(default=5.0, gt=0)
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    max_concurrent_requests: int = Field(default=10, ge=1, le=100)
    rate_limit_per_host: float = Field(default=1.0, gt=0)
    respect_robots_txt: bool = True
    follow_cross_origin: bool = False
    max_pages: int = Field(default=1000, ge=1, le=10000)
    depth_limit: int = Field(default=5, ge=0)
    visited_cache_size: int = Field(default=100_000, ge=100)
    max_retries: int = Field(default=2, ge=0)
    retry_backoff_seconds: float = Field(default=0.5, ge=0)
    allow_localhost: bool = False
    max_redirects: int = Field(default=10, ge=0, le=50)
    max_response_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)

    @model_validator(mode="after")
    def validate_limits(self):
        if self.follow_cross_origin and not self.respect_robots_txt:
            raise ValueError("cross-origin crawling requires robots.txt compliance")
        return self


class AuditSettings(SecretSafeModel):
    """Technical SEO audit thresholds and feature flags."""

    enable_p0_rules: bool = True
    enable_p1_rules: bool = True
    enable_p2_rules: bool = False
    max_depth_for_link_analysis: int = Field(default=10, ge=0)
    pagerank_damping: float = Field(default=0.85, gt=0, lt=1)
    max_iterations: int = Field(default=100, ge=1, le=10000)
    threshold_dead_end: int = Field(default=0, ge=0)
    threshold_thin_page: int = Field(default=2, ge=0)


class DatabaseSettings(SecretSafeModel):
    """Database connection and pool settings."""

    url: str = "sqlite+aiosqlite:///./sie.db"
    auto_migrate: bool = True
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=10, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=1)
    pool_recycle: int = Field(default=1800, ge=0)


class APISettings(SecretSafeModel):
    """API authentication settings."""

    enabled: bool = False
    api_keys: tuple[str, ...] = ()
    header_name: str = "X-API-Key"


class SearchProviderSettings(SecretSafeModel):
    """Generic HTTP search provider settings."""

    enabled: bool = False
    provider_name: str = "http"
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = Field(default=30.0, gt=0)
    connect_timeout_seconds: float = Field(default=5.0, gt=0)
    read_timeout_seconds: float = Field(default=30.0, gt=0)
    write_timeout_seconds: float = Field(default=10.0, gt=0)
    pool_timeout_seconds: float = Field(default=5.0, gt=0)
    allow_localhost: bool = False


class SerpAPISettings(SecretSafeModel):
    """SerpAPI cost and quota policy."""

    request_cost_usd: float = Field(default=0.0, ge=0)
    monthly_request_limit: int = Field(default=0, ge=0)
    quota_key: str = "serpapi"


class SearchConsoleSettings(SecretSafeModel):
    """Google Search Console credentials and property configuration."""

    enabled: bool = False
    property_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    access_token: str = ""
    timeout_seconds: float = Field(default=20.0, gt=0)


class AnalyticsSettings(SecretSafeModel):
    """Google Analytics 4 Data API credentials and configuration."""

    enabled: bool = False
    property_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    access_token: str = ""
    timeout_seconds: float = Field(default=20.0, gt=0)


class BacklinkSettings(SecretSafeModel):
    """Backlink provider settings."""

    enabled: bool = False
    provider_name: str = "dataforseo"
    base_url: str = "https://api.dataforseo.com"
    login: str = ""
    password: str = ""
    timeout_seconds: float = Field(default=30.0, gt=0)
    include_subdomains: bool = True
    exclude_internal_backlinks: bool = True


class LLMSettings(SecretSafeModel):
    """Optional LLM provider settings."""

    enabled: bool = False
    base_url: str = "https://api.openai.com"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout_seconds: float = Field(default=60.0, gt=0)
    connect_timeout_seconds: float = Field(default=10.0, gt=0)
    read_timeout_seconds: float = Field(default=60.0, gt=0)
    write_timeout_seconds: float = Field(default=30.0, gt=0)
    pool_timeout_seconds: float = Field(default=10.0, gt=0)
    max_tokens: int = Field(default=4096, ge=1)
    temperature: float = Field(default=0.3, ge=0, le=2)


class CrUXSettings(SecretSafeModel):
    """Chrome UX Report API settings."""

    enabled: bool = False
    api_key: str = ""
    timeout_seconds: float = Field(default=10.0, gt=0)
    form_factor: str = "PHONE"


class CacheSettings(SecretSafeModel):
    """Optional Redis-backed search response cache."""

    enabled: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"
    key_prefix: str = "sie:"
    response_ttl_seconds: int = Field(default=86400, ge=1)
    max_memory_entries: int = Field(default=10_000, ge=1)
    connect_timeout_seconds: float = Field(default=2.0, gt=0)


class JobSettings(SecretSafeModel):
    """Durable background-job worker settings."""

    enabled: bool = True
    poll_interval_seconds: float = Field(default=1.0, gt=0)
    lease_seconds: int = Field(default=300, ge=1)
    max_attempts: int = Field(default=3, ge=1)
    concurrency: int = Field(default=2, ge=1, le=32)


class Settings(BaseSettings, SecretSafeModel):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_prefix="SIE_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: EnvironmentName = "development"
    debug: bool = True
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    version: str = __version__

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    api: APISettings = Field(default_factory=APISettings)
    search_provider: SearchProviderSettings = Field(default_factory=SearchProviderSettings)
    serpapi: SerpAPISettings = Field(default_factory=SerpAPISettings)
    search_console: SearchConsoleSettings = Field(default_factory=SearchConsoleSettings)
    analytics: AnalyticsSettings = Field(default_factory=AnalyticsSettings)
    backlinks: BacklinkSettings = Field(default_factory=BacklinkSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    crux: CrUXSettings = Field(default_factory=CrUXSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    jobs: JobSettings = Field(default_factory=JobSettings)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def validate_environment(self):
        if self.is_production and self.debug:
            raise ValueError("SIE_DEBUG must be false in production")
        if self.is_production and self.database.auto_migrate:
            raise ValueError("SIE_DATABASE__AUTO_MIGRATE must be false in production")
        if self.is_production and not self.api.enabled and not self.api.api_keys:
            # Production can run behind an authenticated upstream gateway, but
            # the explicit API-key list must still remain empty when disabled.
            pass
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
