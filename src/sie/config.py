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

    auto_migrate: bool = True

    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    content: ContentSettings = Field(default_factory=ContentSettings)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton; tests construct ``Settings`` directly instead."""
    return Settings()
