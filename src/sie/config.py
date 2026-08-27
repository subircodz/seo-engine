"""Application settings.

All runtime configuration comes from the environment (optionally via a local
``.env`` file). Every variable is prefixed with ``SIE_``; nested models use
``__`` as the delimiter (e.g. ``SIE_CRAWLER__MAX_PAGES``).
"""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from sie import __version__

EnvironmentName = Literal["development", "test", "production"]


class CrawlerSettings(BaseModel):
    """Politeness and scope defaults consumed by the Crawler Engine."""

    user_agent: str = "Mozilla/5.0 (compatible; SEOIntelligenceEngine/0.1)"

    # Granular timeouts (seconds)
    connect_timeout_seconds: float = Field(default=5.0, gt=0)
    read_timeout_seconds: float = Field(default=20.0, gt=0)
    write_timeout_seconds: float = Field(default=10.0, gt=0)
    pool_timeout_seconds: float = Field(default=5.0, gt=0)

    # Legacy single timeout (used if granular not set)
    request_timeout_seconds: float = Field(default=20.0, gt=0)

    max_concurrent_requests: int = Field(default=10, ge=1)
    rate_limit_per_host: float = Field(default=1.0, gt=0)
    respect_robots_txt: bool = True
    follow_cross_origin: bool = False
    max_pages: int = Field(default=1000, ge=1)
    depth_limit: int = Field(default=5, ge=0)
    visited_cache_size: int = Field(default=100_000, ge=100)
    max_retries: int = Field(default=2, ge=0)
    retry_backoff_seconds: float = Field(default=0.5, gt=0)

    # SSRF protection: allow localhost/private IPs (dev only)
    allow_localhost: bool = False


class CloudflareBypassSettings(BaseModel):
    """Cloudflare bypass settings for crawler engine.

    When enabled, the crawler will automatically detect Cloudflare challenges
    and bypass them using SeleniumBase + Playwright CDP session hijacking.
    """

    enabled: bool = False
    headless: bool = True
    browser_timeout_seconds: float = Field(default=30.0, gt=0)
    browser_wait_seconds: float = Field(default=10.0, gt=0)
    max_browser_retries: int = Field(default=2, ge=1)


class AuditSettings(BaseModel):
    """Technical SEO + link-graph engine tuning."""

    enable_p0_rules: bool = True
    enable_p1_rules: bool = True
    enable_p2_rules: bool = False
    max_depth_for_link_analysis: int = Field(default=10, ge=1)
    pagerank_damping: float = Field(default=0.85, gt=0, lt=1)
    max_iterations: int = Field(default=100, ge=1)
    threshold_dead_end: int = 0
    threshold_thin_page: int = 2


class ContentSettings(BaseModel):
    """Content Intelligence engine tuning."""

    min_word_count: int = Field(default=300, ge=0)
    thin_content_threshold: int = Field(default=150, ge=0)
    duplicate_similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    near_duplicate_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    keyword_stuffing_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    max_keywords: int = Field(default=50, ge=1)
    enable_readability: bool = True
    enable_keywords: bool = True
    enable_comparison: bool = True
    stopwords_language: str = "en"


class LLMSettings(BaseModel):
    """LLM provider configuration.

    All values are read from environment variables prefixed with ``SIE_LLM__``.
    The provider is disabled by default; set ``enabled=true`` and provide a
    ``base_url`` + ``api_key`` to activate LLM-enhanced diagnosis.
    """

    enabled: bool = False
    base_url: str = "https://api.openai.com"
    api_key: str = ""
    model: str = "gpt-4o-mini"

    # Granular timeouts (seconds)
    connect_timeout_seconds: float = Field(default=10.0, gt=0)
    read_timeout_seconds: float = Field(default=60.0, gt=0)
    write_timeout_seconds: float = Field(default=30.0, gt=0)
    pool_timeout_seconds: float = Field(default=10.0, gt=0)

    # Legacy single timeout
    timeout_seconds: float = Field(default=60.0, gt=0)

    max_tokens: int = Field(default=4096, ge=256)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)


class SearchProviderCapabilitySettings(BaseModel):
    """Settings for a single capability-specific search provider.

    All values are read from environment variables prefixed with
    ``SIE_SEARCH_PROVIDER__{CAPABILITY}__`` (e.g. ``SIE_SEARCH_PROVIDER__AIO__PROVIDER_NAME``).

    When omitted, the capability falls back to the legacy single-provider settings.
    """

    provider_name: str = "mock"
    base_url: str = ""
    api_key: str = ""

    # Granular timeouts (seconds)
    connect_timeout_seconds: float = Field(default=5.0, gt=0)
    read_timeout_seconds: float = Field(default=30.0, gt=0)
    write_timeout_seconds: float = Field(default=10.0, gt=0)
    pool_timeout_seconds: float = Field(default=5.0, gt=0)

    # Legacy single timeout (used if granular not set)
    timeout_seconds: float = Field(default=30.0, gt=0)

    # SSRF protection: allow localhost/private IPs (dev only)
    allow_localhost: bool = False


class SearchProviderSettings(BaseModel):
    """Search provider configuration.

    All values are read from environment variables prefixed with
    ``SIE_SEARCH_PROVIDER__``.  The provider is disabled by default;
    set ``enabled=true`` and provide ``provider_name`` to activate
    search-ranking collection via an external provider.

    When disabled, the application falls back to the in-memory
    ``MockSearchProvider`` (no network I/O, useful for development
    and testing).

    ``api_key`` is optional — some providers (local services,
    OpenAI-compatible gateways, internal APIs) do not require one.
    When omitted or empty, the provider implementation must handle
    authentication-free operation gracefully.

    Capability-specific providers can be configured via nested settings:
    - ``rankings``: provider for search/ranking collection
    - ``aio``: provider for AI Overview extraction
    - ``geo``: provider for Generative Engine queries

    When a capability is not configured, it falls back to the legacy
    single-provider settings.
    """

    enabled: bool = False
    provider_name: str = "mock"
    base_url: str = ""
    api_key: str = ""

    # Granular timeouts (seconds)
    connect_timeout_seconds: float = Field(default=5.0, gt=0)
    read_timeout_seconds: float = Field(default=30.0, gt=0)
    write_timeout_seconds: float = Field(default=10.0, gt=0)
    pool_timeout_seconds: float = Field(default=5.0, gt=0)

    # Legacy single timeout
    timeout_seconds: float = Field(default=30.0, gt=0)

    # SSRF protection: allow localhost/private IPs (dev only)
    allow_localhost: bool = False

    # Capability-specific provider settings (optional)
    rankings: SearchProviderCapabilitySettings | None = None
    aio: SearchProviderCapabilitySettings | None = None
    geo: SearchProviderCapabilitySettings | None = None
    # LLM settings for GEO provider (used when GEO provider is "llm")
    llm: LLMSettings | None = None

    def _masked_key(self) -> str:
        """Return masked API key for safe display."""
        return "'***'" if self.api_key else "''"

    def __repr__(self) -> str:
        """Mask the API key to prevent accidental secret leakage in logs."""
        return (
            f"SearchProviderSettings(enabled={self.enabled!r}, "
            f"provider_name={self.provider_name!r}, "
            f"base_url={self.base_url!r}, "
            f"api_key={self._masked_key()}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"rankings={self.rankings!r}, "
            f"aio={self.aio!r}, "
            f"geo={self.geo!r}, "
            f"llm={self.llm!r})"
        )

    def __str__(self) -> str:
        """Mask the API key to prevent accidental secret leakage in str()."""
        return self.__repr__()


class CruxSettings(BaseModel):
    """Chrome User Experience Report (CrUX) API configuration.

    All values are read from environment variables prefixed with
    ``SIE_CRUX__``.

    The CrUX API provides real-user Core Web Vitals data from Chrome users.
    Requires a Google Cloud API key with Chrome UX Report API enabled.
    """

    enabled: bool = False
    api_key: str = ""
    timeout_seconds: float = Field(default=10.0, gt=0)
    form_factor: str = "PHONE"  # PHONE, DESKTOP, TABLET

    def __repr__(self) -> str:
        key_display = "'***'" if self.api_key else "''"
        return (
            f"CruxSettings(enabled={self.enabled!r}, "
            f"api_key={key_display}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )

    def __str__(self) -> str:
        """Mask the API key to prevent accidental secret leakage in logs."""
        return self.__repr__()


class DatabaseSettings(BaseModel):
    """Database connection pool configuration."""

    # Connection pool settings (PostgreSQL)
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=10, ge=0, le=100)
    pool_timeout: float = Field(default=30.0, gt=0)
    pool_recycle: int = Field(default=1800, ge=0)  # seconds

    # Auto-migration behavior
    auto_migrate: bool = True


class APISettings(BaseModel):
    """API authentication configuration."""

    enabled: bool = False
    api_keys: list[str] = Field(default_factory=list)
    header_name: str = "X-API-Key"


class LimitSettings(BaseModel):
    """Request/response size limits for API endpoints."""

    max_import_records: int = Field(default=10000, ge=1)
    max_collect_queries: int = Field(default=500, ge=1)
    max_analysis_observations: int = Field(default=5000, ge=1)
    max_industry_content_chars: int = Field(default=100000, ge=1)
    max_aio_observations: int = Field(default=1000, ge=1)
    max_geo_observations: int = Field(default=1000, ge=1)


class Settings(BaseSettings):
    """Root configuration object. Construct directly (with overrides) in tests."""

    model_config = SettingsConfigDict(
        env_prefix="SIE_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SEO Intelligence Engine"
    version: str = __version__
    environment: EnvironmentName = "development"
    debug: bool = True
    log_level: str = "INFO"

    host: str = "127.0.0.1"
    port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./sie.db"

    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    content: ContentSettings = Field(default_factory=ContentSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    search_provider: SearchProviderSettings = Field(default_factory=SearchProviderSettings)
    cloudflare_bypass: CloudflareBypassSettings = Field(default_factory=CloudflareBypassSettings)
    crux: CruxSettings = Field(default_factory=CruxSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    limits: LimitSettings = Field(default_factory=LimitSettings)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def auto_migrate(self) -> bool:
        """Auto-migrate defaults to False in production for safety."""
        if self.is_production:
            return self.database.auto_migrate
        return self.database.auto_migrate


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton; tests construct ``Settings`` directly instead."""
    return Settings()
