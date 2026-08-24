"""FastAPI application factory -- the Phase 3 composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sie.api.routes import audit, content, crawl, diagnosis, intelligence, search, system, web
from sie.config import Settings, get_settings
from sie.domain.services.audit_service import AuditService
from sie.domain.services.content_service import ContentService
from sie.domain.services.crawl_service import CrawlService
from sie.domain.services.diagnosis_service import DiagnosisService
from sie.domain.services.intelligence_service import IntelligenceService
from sie.infrastructure.crawling.engine import HttpxCrawlerEngine
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher
from sie.infrastructure.fetching.retrying_fetcher import RetryingFetcher
from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider
from sie.infrastructure.parsing.html_parser import Bs4PageParser
from sie.infrastructure.persistence.database import Database
from sie.infrastructure.persistence.migrations import run_migrations
from sie.infrastructure.persistence.repositories import SqlAlchemyCrawlRunRepository
from sie.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _log_event_factory():
    def _log(event):
        logger.info("crawl event: %s", event)

    return _log


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    logger.info(
        "configuring %s v%s (%s)", settings.app_name, settings.version, settings.environment
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.database = Database(settings.database_url)
        logger.info("database driver: %s", settings.database_url.split("://")[0])

        if settings.auto_migrate:
            run_migrations(settings.database_url)

        cs = settings.crawler
        fetcher = RetryingFetcher(
            HttpxFetcher(user_agent=cs.user_agent, timeout_seconds=cs.request_timeout_seconds),
            max_retries=cs.max_retries,
            base_delay_seconds=cs.retry_backoff_seconds,
        )
        engine = HttpxCrawlerEngine(
            fetcher=fetcher,
            user_agent=cs.user_agent,
            max_concurrency=cs.max_concurrent_requests,
            rate_limit_per_host=cs.rate_limit_per_host,
            respect_robots_txt=cs.respect_robots_txt,
            follow_cross_origin=cs.follow_cross_origin,
            visited_cache_size=cs.visited_cache_size,
        )
        repo = SqlAlchemyCrawlRunRepository(app.state.database.session_factory)
        app.state.crawled_pages = {}  # run_id -> list[FetchedPage]
        app.state.crawl_service = CrawlService(
            engine, repo, handlers=[_log_event_factory()], pages_store=app.state.crawled_pages
        )
        app.state.fetcher = fetcher
        app.state.audit_service = AuditService(repo, Bs4PageParser())
        app.state.content_service = ContentService(repo, Bs4PageParser())
        app.state.diagnosis_service = DiagnosisService(repo, Bs4PageParser())

        # LLM provider — conditionally created
        llm_provider = None
        llm_cfg = settings.llm
        if llm_cfg.enabled:
            llm_provider = OpenAICompatibleProvider(
                base_url=llm_cfg.base_url,
                api_key=llm_cfg.api_key,
                model=llm_cfg.model,
                timeout_seconds=llm_cfg.timeout_seconds,
            )
            logger.info(
                "LLM provider enabled: model=%s base_url=%s",
                llm_cfg.model,
                llm_cfg.base_url,
            )
        else:
            logger.info("LLM provider disabled (set SIE_LLM__ENABLED=true)")
        app.state.llm_provider = llm_provider
        app.state.intelligence_service = IntelligenceService(
            llm_provider,
            model_name=llm_cfg.model if llm_cfg.enabled else "deterministic",
            provider_name=llm_cfg.base_url if llm_cfg.enabled else "none",
        )
        app.state.repository = repo

        # Search provider — conditionally created based on configuration
        sp_cfg = settings.search_provider
        if not sp_cfg.enabled:
            logger.info("Search provider disabled (set SIE_SEARCH_PROVIDER__ENABLED=true)")
            from sie.infrastructure.search.mock_provider import MockSearchProvider

            app.state.search_provider = MockSearchProvider()
        elif sp_cfg.provider_name == "mock":
            from sie.infrastructure.search.mock_provider import MockSearchProvider

            app.state.search_provider = MockSearchProvider()
        elif sp_cfg.provider_name == "http":
            from sie.infrastructure.search.http_provider import HttpSearchProvider

            if not sp_cfg.base_url:
                raise ValueError("Search provider 'http' requires SIE_SEARCH_PROVIDER__BASE_URL")
            app.state.search_provider = HttpSearchProvider(
                base_url=sp_cfg.base_url,
                api_key=sp_cfg.api_key,
                timeout_seconds=sp_cfg.timeout_seconds,
            )
            logger.info(
                "Search provider enabled: name=%s base_url=%s",
                sp_cfg.provider_name,
                sp_cfg.base_url,
            )
        else:
            raise ValueError(
                f"Unknown search provider {sp_cfg.provider_name!r}. "
                "Supported providers: 'mock', 'http'"
            )

        logger.info("startup complete")
        yield

        await app.state.crawl_service.shutdown()
        await fetcher.close()
        if llm_provider is not None:
            await llm_provider.close()
        await app.state.database.dispose()
        logger.info("shutdown complete")

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.include_router(audit.router)
    app.include_router(content.router)
    app.include_router(crawl.router)
    app.include_router(diagnosis.router)
    app.include_router(intelligence.router)
    app.include_router(search.router)
    app.include_router(system.router)
    app.include_router(web.router)
    return app
