"""FastAPI application factory and production composition root."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from sie.api.routes import (audit, content, crawl, diagnosis, intelligence, jobs, report, search, search_intelligence, search_performance, site_analysis, system, web)
from sie.config import Settings, get_settings
from sie.domain.services.audit_service import AuditService
from sie.domain.services.content_service import ContentService
from sie.domain.services.crawl_service import CrawlService
from sie.domain.services.diagnosis_service import DiagnosisService
from sie.domain.services.industry_intelligence import IndustryIntelligenceService
from sie.domain.services.intelligence_service import IntelligenceService
from sie.domain.services.site_analysis import create_site_analysis_service
from sie.infrastructure.crawling.engine import HttpxCrawlerEngine
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher
from sie.infrastructure.fetching.retrying_fetcher import RetryingFetcher
from sie.infrastructure.external_provider_factory import create_external_providers
from sie.infrastructure.jobs.durable_queue import DurableJobQueue
from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider
from sie.infrastructure.parsing.html_parser import Bs4PageParser
from sie.infrastructure.persistence.database import Database
from sie.infrastructure.persistence.migrations import run_migrations
from sie.infrastructure.persistence.repositories import SqlAlchemyCrawlRunRepository
from sie.logging import get_logger, set_request_id, setup_logging

logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and track request IDs for correlation."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            set_request_id(None)


def _log_event_factory():
    def _log(event):
        logger.info("crawl event: %s", event)
    return _log


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    logger.info("configuring %s v%s (%s)", settings.app_name, settings.version, settings.environment)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        db_cfg = settings.database
        app.state.database = Database(settings.database_url, pool_size=db_cfg.pool_size, max_overflow=db_cfg.max_overflow, pool_timeout=db_cfg.pool_timeout, pool_recycle=db_cfg.pool_recycle)
        if settings.auto_migrate:
            run_migrations(settings.database_url)

        cs = settings.crawler
        cf_bypass = settings.cloudflare_bypass
        fetcher = RetryingFetcher(
            HttpxFetcher(user_agent=cs.user_agent, timeout_seconds=cs.request_timeout_seconds, connect_timeout_seconds=cs.connect_timeout_seconds, read_timeout_seconds=cs.read_timeout_seconds, write_timeout_seconds=cs.write_timeout_seconds, pool_timeout_seconds=cs.pool_timeout_seconds, allow_localhost=cs.allow_localhost),
            max_retries=cs.max_retries,
            base_delay_seconds=cs.retry_backoff_seconds,
        )
        if cf_bypass.enabled:
            from sie.infrastructure.crawling.cloudflare_bypass_engine import CloudflareBypassCrawlerEngine
            engine = CloudflareBypassCrawlerEngine(fetcher=fetcher, user_agent=cs.user_agent, max_concurrency=cs.max_concurrent_requests, rate_limit_per_host=cs.rate_limit_per_host, respect_robots_txt=cs.respect_robots_txt, follow_cross_origin=cs.follow_cross_origin, visited_cache_size=cs.visited_cache_size, enable_bypass=True, browser_timeout_seconds=cf_bypass.browser_timeout_seconds, browser_wait_seconds=cf_bypass.browser_wait_seconds, headless=cf_bypass.headless, max_browser_retries=cf_bypass.max_browser_retries)
        else:
            engine = HttpxCrawlerEngine(fetcher=fetcher, user_agent=cs.user_agent, max_concurrency=cs.max_concurrent_requests, rate_limit_per_host=cs.rate_limit_per_host, respect_robots_txt=cs.respect_robots_txt, follow_cross_origin=cs.follow_cross_origin, visited_cache_size=cs.visited_cache_size)

        repo = SqlAlchemyCrawlRunRepository(app.state.database.session_factory)
        app.state.crawled_pages = {}
        app.state.fetcher = fetcher
        app.state.crawl_service = CrawlService(engine, repo, handlers=[_log_event_factory()], pages_store=app.state.crawled_pages)
        app.state.audit_service = AuditService(repo, Bs4PageParser())
        app.state.content_service = ContentService(repo, Bs4PageParser())
        app.state.diagnosis_service = DiagnosisService(repo, Bs4PageParser())

        llm_provider = None
        llm_cfg = settings.llm
        if llm_cfg.enabled:
            llm_provider = OpenAICompatibleProvider(base_url=llm_cfg.base_url, api_key=llm_cfg.api_key, model=llm_cfg.model, timeout_seconds=llm_cfg.timeout_seconds, connect_timeout_seconds=llm_cfg.connect_timeout_seconds, read_timeout_seconds=llm_cfg.read_timeout_seconds, write_timeout_seconds=llm_cfg.write_timeout_seconds, pool_timeout_seconds=llm_cfg.pool_timeout_seconds)
        app.state.llm_provider = llm_provider
        app.state.intelligence_service = IntelligenceService(llm_provider, model_name=llm_cfg.model if llm_cfg.enabled else "deterministic", provider_name=llm_cfg.base_url if llm_cfg.enabled else "none")
        app.state.repository = repo
        app.state.industry_intelligence_service = IndustryIntelligenceService()

        from sie.infrastructure.search.provider_factory import create_provider_registry
        app.state.search_provider = create_provider_registry(settings.search_provider, serpapi_settings=settings.serpapi, cache_settings=settings.cache)

        from sie.infrastructure.crux import CruxService
        app.state.crux_service = CruxService(api_key=settings.crux.api_key if settings.crux.enabled else None, timeout_seconds=settings.crux.timeout_seconds, form_factor=settings.crux.form_factor)
        app.state.site_analysis_service = create_site_analysis_service(crawl_service=app.state.crawl_service, audit_service=app.state.audit_service, content_service=app.state.content_service, search_provider=app.state.search_provider, repository=app.state.repository, crux_service=app.state.crux_service)

        # Real external data providers are constructed once and kept in app state.
        # They do not perform network I/O until explicitly queried by an analysis service.
        app.state.external_providers = create_external_providers(settings)

        app.state.job_queue = DurableJobQueue(app.state.database.session_factory, lease_seconds=settings.jobs.lease_seconds, max_attempts=settings.jobs.max_attempts)

        async def run_site_analysis(payload: dict):
            result = await app.state.site_analysis_service.analyze_site(**payload)
            return {"domain": result.domain, "crawl_run_id": result.crawl_run_id, "overall_score": result.overall_score, "analyzed_at": result.analyzed_at.isoformat()}

        app.state.job_queue.register("site-analysis", run_site_analysis)
        app.state.job_stop_event = asyncio.Event()
        app.state.job_workers = []
        if settings.jobs.enabled:
            for index in range(settings.jobs.concurrency):
                app.state.job_workers.append(asyncio.create_task(app.state.job_queue.run_worker(f"sie-worker-{uuid.uuid4().hex[:12]}-{index}", poll_interval_seconds=settings.jobs.poll_interval_seconds, stop_event=app.state.job_stop_event)))

        logger.info("startup complete")
        yield

        app.state.job_stop_event.set()
        if app.state.job_workers:
            await asyncio.gather(*app.state.job_workers, return_exceptions=True)
        await app.state.crawl_service.shutdown()
        await fetcher.close()
        if llm_provider is not None:
            await llm_provider.close()
        close_provider = getattr(app.state.search_provider, "close", None)
        if close_provider is not None:
            await close_provider()
        for provider in app.state.external_providers.values():
            if provider is not None:
                close = getattr(provider, "close", None)
                if close is not None:
                    await close()
        await app.state.database.dispose()
        logger.info("shutdown complete")

    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan, docs_url=None if settings.is_production else "/docs", redoc_url=None)
    app.add_middleware(RequestIdMiddleware)
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(audit.router)
    app.include_router(content.router)
    app.include_router(crawl.router)
    app.include_router(diagnosis.router)
    app.include_router(intelligence.router)
    app.include_router(jobs.router)
    app.include_router(report.router)
    app.include_router(search.router)
    app.include_router(search_intelligence.router)
    app.include_router(search_performance.router)
    app.include_router(site_analysis.router)
    app.include_router(system.router)
    app.include_router(web.router)
    return app
