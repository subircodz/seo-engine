# Changelog

All notable changes to the SEO Intelligence Engine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **SSRF Protection**: Added comprehensive Server-Side Request Forgery protection for all outbound HTTP requests
  - New `src/sie/domain/security/ssrf.py` module with validation utilities
  - Blocks private IP ranges (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16)
  - Blocks cloud metadata endpoints (169.254.169.254, fd00:ec2::254)
  - Blocks IPv6 link-local, ULA, and multicast ranges
  - Validates URL schemes (only http/https allowed)
  - Validates redirect targets to prevent DNS rebinding
  - Configurable `allow_localhost` setting for development (default: false)
  - Applied to `HttpSearchProvider` (validates `base_url` at construction) and `HttpxFetcher` (validates each request and redirect)

- **API Key Authentication**: Minimal, configurable API key authentication layer
  - New `src/sie/api/auth.py` with constant-time key comparison using `secrets.compare_digest`
  - Supports multiple valid API keys
  - Disabled by default (`SIE_API__ENABLED=false`) for development
  - `X-API-Key` header authentication for all `/api/*` endpoints
  - Web UI routes (`/`, `/search`, `/datasets`, etc.) remain unauthenticated
  - Health endpoint (`/health`) and OpenAPI docs (`/docs`) remain public

- **Production Database Configuration**: PostgreSQL connection pooling and safe migration defaults
  - New `DatabaseSettings` in config with pool configuration (`pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`)
  - `Database` class applies pool settings only for PostgreSQL (not SQLite)
  - Auto-migrate defaults to `false` in production environment
  - Health check verifies pool connectivity

- **Resource/Request Limits**: Configurable limits on expensive API endpoints
  - New `LimitSettings` in config with per-endpoint limits
  - `/api/search/import/json` - max 10,000 records
  - `/api/search/datasets/{id}/collect` - max 500 queries
  - `/api/search-intelligence/analyze` - max 5,000 observations
  - `/api/search-intelligence/industry/analyze` - max 100,000 content characters
  - `/api/search-intelligence/aio/analyze` - max 1,000 observations
  - `/api/search-intelligence/geo/analyze` - max 1,000 observations
  - Returns 413 Payload Too Large with clear error messages

- **HTTP Timeout Robustness**: Granular timeout configuration
  - Added `connect_timeout`, `read_timeout`, `write_timeout`, `pool_timeout` to `CrawlerSettings`, `SearchProviderSettings`, `LLMSettings`
  - Uses `httpx.Timeout(connect=..., read=..., write=..., pool=...)` for all HTTP clients
  - Sensible defaults: connect=5s, read=30s, write=10s, pool=5s
  - No new retries introduced (non-idempotent operations remain unsafe to retry)

- **Async-Safe PDF Rendering**: Offloaded WeasyPrint to thread pool
  - New `PDFRenderer.render_async()` method using `asyncio.run_in_executor()`
  - Prevents CPU-heavy PDF generation from blocking the event loop
  - Backward-compatible synchronous `render()` method retained

- **Request Correlation IDs**: Full request tracing through logs
  - New middleware adds `X-Request-ID` header to all responses
  - Request ID available in `request.state.request_id`
  - Logging filter injects `request_id` into all log records
  - Context variable for async-safe request ID propagation

- **Crawl Content Persistence**: HTML content now survives process restarts
  - Added `html_content` (LargeBinary) column to `crawl_pages` table
  - `CrawlPageRecord` model includes `html_content: bytes | None`
  - `HttpxCrawlerEngine` stores raw HTML content via `page.content`
  - `CrawlService` persists HTML content for downstream intelligence (audit, content, diagnosis)
  - Alembic migration `5e4c59abfe15` adds `html_content` column

- **Industry Intelligence Correctness Fixes**: Fixed false positives in entity extraction
  - Casino engine: `_PATTERN_GAME_NAME` now only matches phrases with casino-related keywords (slot, roulette, blackjack, etc.)
  - Removed domain classification as `CASINO` entity type (domains are not casino entities)
  - Removed confidence boost for "." in text (was incorrectly boosting domains)
  - Game providers (NetEnt, Pragmatic, etc.) and currencies (BTC, ETH) extracted via dedicated patterns
  - Added `test_domain_not_extracted` regression test

- **Product Identity**: Professional branding throughout UI
  - Navigation brand changed from "SIE" to "SEO Intelligence Engine"
  - Footer updated with copyright: "© 2026 Subir Sutradhar"
  - Maintains glassmorphism dark-mode-first design

- **License**: Apache-2.0 license adopted
  - Added `LICENSE` file with full Apache License 2.0 text
  - Updated `pyproject.toml` with `license = { text = "Apache-2.0" }` and classifier
  - Updated `README.md` with license badge and link

### Changed
- `SearchProviderSettings`: Added `allow_localhost`, granular timeouts
- `CrawlerSettings`: Added `allow_localhost`, granular timeouts
- `LLMSettings`: Added granular timeouts
- `config.py`: Added `DatabaseSettings`, `APISettings`, `LimitSettings`
- `HttpSearchProvider`: Validates `base_url` at construction, uses granular timeouts
- `HttpxFetcher`: Validates request URLs and redirects, uses granular timeouts
- `OpenAICompatibleProvider`: Uses granular timeouts
- `Database`: Applies connection pooling for PostgreSQL
- `PDFRenderer`: Added `render_async()` for non-blocking PDF generation
- `CrawlPageRecord`: Added `html_content: bytes | None` field
- `CrawlPageRow`: Added `html_content` LargeBinary column
- `CrawlService`: Persists HTML content for downstream intelligence
- `base.html`: Brand changed to "SEO Intelligence Engine", footer updated with copyright

### Fixed
- Casino entity extraction no longer produces false positives for generic capitalized phrases
- Domain names no longer incorrectly classified as casino entities
- Confidence scoring no longer inflated for domain-like strings
- Industry intelligence tests updated to reflect corrected behavior

### Security
- SSRF protection blocks access to internal services, cloud metadata, and private networks
- API keys compared using constant-time comparison to prevent timing attacks
- API keys never logged or exposed in error messages
- Request/response size limits prevent resource exhaustion

### Tests
- Added 15+ SSRF protection test cases (blocked ranges, redirects, localhost toggle)
- Added 5 API authentication test cases (missing, invalid, valid, public, protected)
- Added 6 resource limit test cases (under/over limits)
- Added 3 provider timeout configuration verification tests
- Added crawl persistence round-trip + restart simulation tests
- Added PDF async rendering non-blocking verification
- Added request ID header and log injection tests
- Added 4 industry intelligence regression tests for corrected behavior
- All 940+ existing unit tests pass
- All integration tests pass

---

## [0.1.0] - 2026-08-25

### Added
- Initial release of SEO Intelligence Engine
- Deterministic SEO, AIO, GEO intelligence engines
- Industry-specific intelligence (Casino, Crypto, Crypto-Casino)
- Evidence/provenance architecture with confidence scoring
- Server-rendered glassmorphism UI with dark/light themes
- Professional PDF reporting via WeasyPrint
- SQLAlchemy + SQLite persistence with Alembic migrations
- Search provider abstraction (Mock + HTTP)
- 40+ REST API endpoints
- Comprehensive test suite (900+ tests)

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.