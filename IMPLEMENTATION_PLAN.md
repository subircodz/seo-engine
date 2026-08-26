# SEO Intelligence Engine — Implementation Plan

## Executive Summary

This plan covers the approved P0-P1 scope items across correctness, security, reliability, AIO/GEO intelligence, and product identity. The codebase is a clean, layered FastAPI application with deterministic domain engines. The plan preserves existing architecture while addressing verified gaps.

---

## Phase 1: Inspection Complete ✓

**Repository structure understood:**
- `src/sie/domain/` — pure models, engines, services, ports (no infra imports)
- `src/sie/infrastructure/` — SQLAlchemy, httpx, WeasyPrint, crawling
- `src/sie/api/` — FastAPI routes, Jinja2 templates (glassmorphism UI)
- `tests/` — unit, integration, intelligence test suites (836+ tests passing)

**Key architectural patterns:**
- Protocol-based ports (`Fetcher`, `SearchProvider`, `Crawler`, `LLMProvider`)
- Dependency injection via `app.state` in lifespan
- Pydantic Settings with `SIE_` prefix
- Alembic migrations for SQLite/PostgreSQL
- Deterministic engines = pure functions, no I/O

---

## Phase 2: Implementation Plan

### P0 — CORRECTNESS AND SECURITY

#### A. Industry Intelligence Correctness Review

**Current state:** Industry intelligence engines (`search_casino.py`, `search_crypto.py`, `search_crypto_casino.py`, `industry_synthesis.py`) are deterministic but may have logic issues.

**Investigation needed:**
1. Review `extract_casino_entities()` regex patterns — `_PATTERN_GAME_NAME` matches any capitalized phrase, causing false positives
2. Review `_classify_casino_entity()` — domain detection (`"." in text`) misclassifies URLs as casinos
3. Review `_estimate_casino_entity_confidence()` — scoring may be inflated
4. Cross-check `IndustryOpportunityScorer.score()` formula for correctness
5. Verify `analyze_casino_content()` gap detection logic

**Deliverables:**
- Bug report with specific incorrect behaviors
- Regression tests for each fixed bug
- Minimal fixes preserving determinism

**Files:** `src/sie/domain/engines/search_casino.py`, `search_crypto.py`, `search_crypto_casino.py`, `industry_synthesis.py`, `tests/unit/test_casino_intelligence.py`, `test_crypto_intelligence.py`, `test_crypto_casino_intelligence.py`, `test_industry_intelligence.py`

---

#### B. SSRF Protection — CRITICAL

**Current vulnerability:** `HttpxFetcher` and `HttpSearchProvider` accept any URL without validation. An attacker controlling a crawl target or search provider `base_url` can probe internal services.

**Threat model (per OWASP SSRF Cheat Sheet):**
- Block: `127.0.0.0/8`, `0.0.0.0/8`, `::1`, `169.254.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- Block IPv6 link-local (`fe80::/10`), ULA (`fc00::/7`), multicast (`ff00::/8`)
- Block cloud metadata: `169.254.169.254`, `[fd00:ec2::254]`
- Validate scheme: only `http`, `https`
- Follow redirects with same validation (DNS rebinding protection)
- Allowlist model where architecture permits (search provider `base_url`)

**Implementation:**

1. **New module:** `src/sie/domain/security/ssrf.py`
   - `is_safe_url(url: str) -> bool` — validates scheme, host, IP ranges
   - `resolve_and_validate(url: str) -> tuple[str, str]` — resolves DNS, validates final IP
   - `SafeHttpClient` wrapper for httpx with redirect validation

2. **Modify `HttpxFetcher.fetch()`** — validate initial URL + each redirect hop
3. **Modify `HttpSearchProvider.__init__()`** — validate `base_url` at construction
4. **Add `SIE_FETCHER__ALLOWED_HOSTS`** allowlist config (optional, for stricter deployments)
5. **Add `SIE_FETCHER__BLOCK_PRIVATE_IPS=true`** config (default true)

**Security regression tests:**
- `tests/unit/test_ssrf_protection.py` — 15+ test cases covering all blocked ranges, redirects, DNS rebinding

**Files:** 
- New: `src/sie/domain/security/ssrf.py`, `tests/unit/test_ssrf_protection.py`
- Modified: `src/sie/infrastructure/fetching/httpx_fetcher.py`, `src/sie/infrastructure/search/http_provider.py`, `src/sie/config.py`

---

#### C. API Authentication

**Current state:** No authentication on any endpoint.

**Scope:** Minimal API key authentication for API routes (not UI routes initially).

**Implementation:**

1. **New settings:** `APIKeySettings` in `config.py`
   - `enabled: bool = False`
   - `api_keys: list[str] = []` (support multiple keys)
   - `header_name: str = "X-API-Key"`

2. **New module:** `src/sie/api/auth.py`
   - `verify_api_key(request: Request) -> bool` — constant-time comparison
   - `api_key_dependency` — FastAPI dependency for protected routes
   - `optional_api_key_dependency` — for endpoints that work with/without key

3. **Apply to API routers:** `search`, `search_intelligence`, `search_performance`, `report`, `crawl`, `audit`, `content`, `diagnosis`, `intelligence`
   - **Exclude:** `system` (health), `web` (UI pages), `docs` (OpenAPI)

4. **Development behavior:** `enabled=False` by default (no auth in dev)
5. **Production behavior:** `enabled=true` requires valid key

**Tests:** `tests/unit/test_api_auth.py` — missing key, invalid key, valid key, public endpoints, protected endpoints

**Files:**
- New: `src/sie/api/auth.py`, `tests/unit/test_api_auth.py`
- Modified: `src/sie/config.py`, `src/sie/api/app.py`, all route files in `src/sie/api/routes/`

---

#### D. Resource/Request Limits

**Current state:** No limits on observations, search requests, analysis payloads.

**Limits to add:**

| Endpoint | Limit | Config |
|----------|-------|--------|
| `/api/search/import/json` | `max_records=10000` | `SIE_LIMITS__MAX_IMPORT_RECORDS` |
| `/api/search/datasets/{id}/collect` | `max_queries=500` | `SIE_LIMITS__MAX_COLLECT_QUERIES` |
| `/api/search-intelligence/analyze` | `max_observations=5000` | `SIE_LIMITS__MAX_ANALYSIS_OBSERVATIONS` |
| `/api/search-intelligence/industry/analyze` | `max_content_chars=100000` | `SIE_LIMITS__MAX_INDUSTRY_CONTENT` |
| `/api/search-intelligence/aio/analyze` | `max_observations=1000` | `SIE_LIMITS__MAX_AIO_OBSERVATIONS` |
| `/api/search-intelligence/geo/analyze` | `max_observations=1000` | `SIE_LIMITS__MAX_GEO_OBSERVATIONS` |

**Implementation:**
- New `LimitsSettings` in `config.py`
- Validation in Pydantic request models (use `Field(le=...)`)
- Return `413 Payload Too Large` with clear error

**Tests:** Verify limits enforced, valid requests pass

**Files:** `src/sie/config.py`, all affected route files, `tests/unit/test_request_limits.py`

---

#### E. External HTTP Timeout Hardening

**Current state:** 
- `HttpxFetcher`: single `timeout_seconds` → `httpx.Timeout(timeout_seconds)` (applies to all phases)
- `HttpSearchProvider`: single `timeout_seconds`
- `RetryingFetcher`: retries on 429/503 + transport errors

**Improvement:** Use granular `httpx.Timeout` with connect/read/write/pool phases.

```python
httpx.Timeout(
    connect=5.0,    # TCP connection
    read=30.0,      # Response body
    write=10.0,     # Request body
    pool=5.0        # Connection pool acquisition
)
```

**Changes:**
1. `CrawlerSettings`: add `connect_timeout`, `read_timeout`, `write_timeout`, `pool_timeout`
2. `SearchProviderSettings`: same granular timeouts
3. `LLMSettings`: same granular timeouts
4. Update `HttpxFetcher`, `HttpSearchProvider`, `OpenAICompatibleProvider` to use granular timeouts
5. **No new retries** — existing `RetryingFetcher` semantics preserved

**Tests:** Verify timeout configuration applied, integration test with slow server

**Files:** `src/sie/config.py`, `src/sie/infrastructure/fetching/httpx_fetcher.py`, `src/sie/infrastructure/search/http_provider.py`, `src/sie/infrastructure/llm/openai_provider.py`, `tests/unit/test_http_timeouts.py`

---

### P1 — PRODUCTION RELIABILITY

#### F. Persistence of Crawl Content

**Current state:** `app.state.crawled_pages = {}` — in-memory dict, lost on restart.

**Required persistence:** Crawl pages needed by downstream intelligence (audit, content, diagnosis) must survive restart.

**Implementation:**
1. **Add `html_content` column** to `CrawlPageRow` (BYTEA/TEXT) — stores raw HTML
2. **Add `decoded_text` column** (optional, for faster re-analysis) — or re-decode on load
3. **Modify `SqlAlchemyCrawlRunRepository.add_page()`** — persist HTML content
4. **Modify `list_pages()`** — return `CrawlPageRecord` with `html_content`
5. **Update `CrawlPageRecord`** model to include `html_content: bytes`
6. **Migration:** `alembic` migration adding columns
7. **CrawlService** already receives `pages_store` — keep in-memory cache for active crawl, but hydrate from DB on startup

**Acceptance:** Crawl data survives restart; `AuditService`, `ContentService`, `DiagnosisService` work with persisted data.

**Tests:** `tests/integration/test_crawl_persistence.py` — round-trip, restart simulation

**Files:** 
- `src/sie/domain/models/crawl.py` (add `html_content`)
- `src/sie/infrastructure/models/crawl_orm.py` (add columns)
- `src/sie/infrastructure/persistence/repositories.py`
- New migration: `migrations/versions/xxx_add_crawl_page_content.py`
- `tests/integration/test_crawl_persistence.py`

---

#### G. Production Database Configuration

**Current state:** SQLite default, basic `Database` class, `auto_migrate=true` default.

**Improvements:**
1. **PostgreSQL connection pooling** — add `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle` to `Database`
2. **Settings:** `DatabaseSettings` with nested pool config
3. **Migration safety:** 
   - `SIE_AUTO_MIGRATE=false` default in production
   - Add `--check` flag to verify pending migrations without applying
   - Document separate `alembic upgrade head` in production
4. **Healthcheck:** verify pool connectivity, not just `SELECT 1`
5. **Keep SQLite dev workflow** — no breaking changes

**Files:** `src/sie/config.py`, `src/sie/infrastructure/persistence/database.py`, `src/sie/infrastructure/persistence/migrations.py`, `.env.example`

---

#### H. PDF Event-Loop Safety

**Current state:** `PDFRenderer._render_html()` calls `weasyprint.HTML(string=html).render()` synchronously in async request path.

**Fix:** Offload to thread pool using `asyncio.to_thread()` or `run_in_executor()`.

**Implementation:**
```python
async def _render_html(self, html: str) -> bytes:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, self._sync_render, html)

def _sync_render(self, html: str) -> bytes:
    doc = self._weasyprint.HTML(string=html).render()
    return doc.write_pdf()
```

**Tests:** `tests/unit/test_pdf_async.py` — verify non-blocking, regression on output

**Files:** `src/sie/domain/renderers/pdf_renderer.py`, `tests/unit/test_pdf_async.py`

---

#### I. Request Correlation

**Current state:** Rich logging, no request IDs.

**Implementation:**
1. **Middleware** in `app.py` — generate UUID per request, add to `request.state.request_id`
2. **Logging filter** — inject `request_id` into log records
3. **Response header** — `X-Request-ID` on all responses
4. **Structured logging** — JSON format option for production

**Minimal approach:** Use existing `logging` + Rich; no logging system replacement.

**Files:** `src/sie/api/app.py` (middleware), `src/sie/logging.py` (filter), `tests/unit/test_request_correlation.py`

---

#### J. Rate Limiting

**Current state:** None.

**Scope:** Minimal token-bucket per IP for expensive endpoints.

**Implementation:**
1. **New module:** `src/sie/api/rate_limit.py` — async token bucket using Redis or in-memory
2. **Settings:** `RateLimitSettings` with `enabled`, `requests_per_minute`, `burst`
3. **Dependency:** `rate_limit_dependency` for protected routes
4. **Apply to:** `/collect`, `/analyze`, `/industry/analyze`, `/import/*`
5. **Development:** disabled by default
6. **Production:** enabled with conservative defaults (e.g., 60 req/min)

**Note:** If Redis not available, use in-memory with warning (single-process only).

**Files:** New `src/sie/api/rate_limit.py`, `src/sie/config.py`, affected routes, `tests/unit/test_rate_limit.py`

---

### 4. AIO / SEO / GEO INTELLIGENCE — EVIDENCE MODEL ENHANCEMENT

**Current state:** AIO/GEO engines produce metrics but lack structured evidence/provenance per finding.

**Goal:** Every finding distinguishes OBSERVED FACT / SOURCE / INTERPRETATION / INFERENCE / CONFIDENCE / RECOMMENDATION.

**Implementation:**

1. **Enhance `Evidence` model** (already exists in `evidence.py`) — ensure it supports:
   - `authority_url` for external sources (Google docs, etc.)
   - `retrieval_date` for external sources
   - `claim` — specific claim from source
   - `evidence_type` — observed/authoritative/analytical/derived

2. **Create `AIOFinding`, `GEOFinding` models** with `Provenance` chain
3. **Update `analyze_aio_observations()`, `analyze_geo_observations()`** to produce findings with evidence
4. **Add official source references** as constants:
   - Google Title Links: `https://developers.google.com/search/docs/appearance/title-link`
   - Google AI Features: `https://developers.google.com/search/docs/appearance/ai-features`
   - Google AI Optimization: `https://developers.google.com/search/docs/fundamentals/ai-optimization-guide`

5. **Language convention:** Use measured phrasing ("may create", "observed signal is", "Google documents that", "insufficient evidence")

**Files:** 
- `src/sie/domain/models/evidence.py` (enhance)
- `src/sie/domain/models/search_aio.py`, `search_geo.py` (add finding models)
- `src/sie/domain/engines/search_aio.py`, `search_geo.py` (produce findings)
- `src/sie/api/routes/search_intelligence.py` (expose findings)
- `tests/unit/test_aio_evidence.py`, `test_geo_evidence.py`

---

### 6. WEB INTERFACE / PRODUCT DESIGN

#### Header/Navigation
- Change brand from "SIE" → "SEO Intelligence Engine"
- Keep abbreviation in tooltip or sub-text: "SIE — SEO Intelligence Engine"

#### Footer
- Update to: `SEO Intelligence Engine · © 2026 Subir Sutradhar · Health · API Docs · License`
- Add license link once decided

#### Report/PDF Branding
- Update `PDFRenderer` template to show "SEO Intelligence Engine"
- Include report ID, generation timestamp, attribution
- Remove "Confidential" unless user context establishes it

#### License Decision
- **Action required:** User must decide license (MIT, Apache-2.0, proprietary, etc.)
- Once decided: update `LICENSE`, `pyproject.toml`, `README.md`, file headers if convention requires

#### README/CHANGELOG
- Update README with actual implemented features (already accurate)
- Create `CHANGELOG.md` from git history

**Files:** `src/sie/templates/base.html`, `src/sie/domain/renderers/pdf_renderer.py`, `README.md`, new `CHANGELOG.md`, `LICENSE`, `pyproject.toml`

---

### 7. UI FINDING PRESENTATION

**Current state:** Basic cards with title, description, recommendation, severity badge.

**Target:** Rich finding cards showing:
```
FINDING: Brand representation inconsistency
OBSERVED: <title>Power.win</title>
EVIDENCE: Crawled HTML, page X
WHY IT MATTERS: ...
SEO IMPACT: ...
AIO IMPACT: ...
GEO IMPACT: ...
CONFIDENCE: Medium
SOURCE: Google Search Central — Title Links
RECOMMENDATION: ...
LIMITATION: ...
```

**Implementation:**
1. **Enhance finding models** to carry structured evidence (see Section 4)
2. **Update `intelligence.html`, `industry.html`** JavaScript renderers
3. **Add CSS** for evidence tags, confidence meter, source links
4. **Preserve glassmorphism design system**

**Files:** `src/sie/templates/intelligence.html`, `industry.html`, `base.html` (CSS additions), `src/sie/api/routes/search_intelligence.py` (enriched response)

---

## Phase 3: Implementation Order (Logical Batches)

| Batch | Items | Rationale |
|-------|-------|-----------|
| 1 | B (SSRF), E (Timeouts) | Security foundations, no dependencies |
| 2 | C (Auth), D (Limits), J (Rate Limit) | API protection layer, can be developed in parallel |
| 3 | F (Crawl Persistence), G (DB Config) | Data layer, requires migration |
| 4 | H (PDF Async), I (Request ID) | Infrastructure improvements |
| 5 | A (Industry Correctness), 4 (AIO/GEO Evidence) | Domain intelligence correctness |
| 6 | 6 (Product Identity), 7 (UI Findings) | User-facing polish |

---

## Dependencies to Add

| Dependency | Purpose | Justification |
|------------|---------|---------------|
| `ipaddress` (stdlib) | IP range validation for SSRF | Standard library, no new dep |
| `secrets` (stdlib) | Constant-time API key comparison | Standard library |
| `redis` (optional) | Rate limiting backend | Only if user wants distributed rate limiting; otherwise in-memory fallback |

**No new heavy dependencies.** All SSRF/auth/rate-limit logic uses stdlib.

---

## Migration Requirements

1. **Crawl page content** — new columns on `crawl_pages` table
2. **Database pool settings** — no schema change, config only
3. **Auth/Rate limit** — no schema change (in-memory or Redis)

---

## Test Plan

| Category | Target |
|----------|--------|
| SSRF tests | 15+ cases (blocked ranges, redirects, rebinding) |
| Auth tests | 5 cases (missing, invalid, valid, public, protected) |
| Request limit tests | 6 endpoints × 2 cases (under/over limit) |
| Timeout tests | 3 providers × granular config verification |
| Crawl persistence | Round-trip + restart simulation |
| PDF async | Non-blocking verification + output regression |
| Request ID | Header present, logs contain ID |
| Rate limit | Bucket exhaustion, burst, recovery |
| Industry correctness | Regression tests for each fixed bug |
| AIO/GEO evidence | Findings have provenance chain |
| UI rendering | Finding cards display all fields |

**Total new tests:** ~60-80 focused tests

**Verification commands:**
```bash
# After each batch
.venv/bin/ruff check src/sie/<touched_module>
.venv/bin/pytest tests/unit/test_<new_tests>.py -v
# Final
.venv/bin/ruff check src/sie
.venv/bin/pytest -x --tb=short
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SSRF breaks legitimate crawls | Low | High | Allowlist config `SIE_FETCHER__ALLOWED_HOSTS` |
| Auth breaks dev workflow | Medium | Medium | Default `enabled=False`, clear docs |
| Crawl persistence migration fails | Low | High | Test migration on copy of production DB first |
| PDF async breaks WeasyPrint | Low | Medium | WeasyPrint is thread-safe; test thoroughly |
| Rate limit false positives | Medium | Medium | Conservative defaults, per-IP not per-user |
| Industry logic changes break tests | Medium | Medium | Write regression tests BEFORE fixes |

---

## Documentation Changes

1. `README.md` — update security, auth, limits sections
2. `CHANGELOG.md` — create from git log
3. `.env.example` — add all new settings with comments
4. `API.md` (new) — document authenticated endpoints, rate limits, error codes
5. Inline docstrings on all new public functions/classes

---

## Remaining Known Limitations (Post-Implementation)

1. **No distributed rate limiting** without Redis (single-process only)
2. **No OAuth/OIDC** — explicitly out of scope
3. **No multi-tenancy** — explicitly out of scope
4. **Crawl JavaScript rendering** — not implemented (Renderer port exists but no impl)
5. **AIO/GEO data collection** — manual observation input only; no automated generative engine API
6. **License** — pending user decision

---

## Deferred Feature Candidates (Report Separately)

- Automated AIO/GEO observation collection via browser automation
- Competitor auto-discovery from SERP overlap
- Scheduled crawl/intelligence runs
- Notification webhooks on ranking changes
- White-label report theming

---

## Approval Request

**Please review and approve this plan before implementation begins.**

Key decisions needed from you:
1. **License choice** (MIT, Apache-2.0, proprietary, other)
2. **Redis for rate limiting?** (yes/no — if no, in-memory with warning)
3. **Crawl HTML persistence size limit?** (recommend 2MB/page, configurable)
4. **Auth on UI routes?** (plan covers API only; UI can be added later)
5. **Request ID format?** (UUID4 recommended)

Once approved, I'll proceed with Batch 1 (SSRF + Timeouts).