# SEO Intelligence Engine (SIE)

A production SEO intelligence platform built in Python. Performs real search-ranking collection, multi-engine intelligence analysis, industry-specific insights, and professional PDF reporting — all through a server-rendered UI with glassmorphism dark-mode-first design.

**Core design principle:** All deterministic analysis is LLM-free. LLMs are optional adapters behind ports, never required for core intelligence.

---

## Features Actually Implemented

| Capability | Status | Description |
|------------|--------|-------------|
| SERP/Ranking Collection | **Real** | Collects rankings via external search API provider |
| Search Analytics | **Real** | Position tracking, visibility scoring, keyword metrics |
| SERP Feature Intelligence | **Real** | 9 feature types, ownership tracking, analytics |
| Cannibalization Detection | **Real** | Multi-URL conflict detection with severity classification |
| Ranking Volatility | **Real** | Position-change volatility scoring |
| Search Opportunities | **Real** | Competitor gaps, weak rankings, content gaps |
| AIO (AI Overview) Intelligence | **Real** | AI search citation/presence analysis |
| GEO (Generative Engine) Intelligence | **Real** | Generative engine entity/mention analysis |
| Performance Intelligence | **Real** | HTML size, resource metrics, content efficiency |
| Entity Intelligence | **Real** | Entity extraction, visibility, competitor gaps |
| Optimization Intelligence | **Real** | Cross-engine synthesis, prioritized recommendations |
| Industry Intelligence | **Real** | Casino, crypto, crypto-casino, general analysis |
| Evidence/Provenance | **Real** | Type/authority classification, confidence scoring |
| PDF Reports | **Real** | Professional PDFs via WeasyPrint |
| Web UI | **Real** | 7 pages, dark/light theme, live API consumption |
| Search Provider Abstraction | **Real** | Protocol-based, vendor-neutral HTTP adapter |
| Persistence | **Real** | SQLAlchemy + SQLite, Alembic migrations |
| REST API | **Real** | 40+ endpoints across search, intelligence, industry |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Interface     FastAPI app, server-rendered HTML (Jinja2),       │
│               glassmorphism UI, REST API, PDF reports           │
├─────────────────────────────────────────────────────────────────┤
│ Application   Service orchestration layer                       │
│               SearchAnalyticsService, IndustryIntelligence,     │
│               SearchIntelligenceService, Performance/Entity/    │
│               Optimization/Reporting services                   │
├─────────────────────────────────────────────────────────────────┤
│ Domain        Immutable models, engines (pure functions),       │
│               ports (Protocols), errors — zero infra imports    │
│                                                           │
│  Engines:     search_analytics, search_aio, search_geo,        │
│               search_performance, search_entity,                │
│               search_optimization, search_report,               │
│               industry_synthesis, casino_intelligence,          │
│               crypto_intelligence, crypto_casino_intelligence   │
├─────────────────────────────────────────────────────────────────┤
│ Infrastructure  SQLAlchemy/SQLite, Alembic migrations,          │
│                 httpx fetcher, search provider adapters,        │
│                 WeasyPrint renderer                             │
└─────────────────────────────────────────────────────────────────┘
```

### Project Layout

```
src/sie/
├── config.py                              # pydantic-settings (SIE_ prefix)
├── api/
│   ├── app.py                             # create_app() composition root
│   ├── routes/
│   │   ├── web.py                         # 7 UI pages
│   │   ├── search.py                      # dataset CRUD, import, analytics
│   │   ├── search_intelligence.py         # AIO, GEO, cannibalization, volatility,
│   │   │                                  #   opportunities, unified intelligence,
│   │   │                                  #   industry intelligence
│   │   ├── search_performance.py          # performance, entity, optimization, report
│   │   ├── report.py                      # PDF download endpoint
│   │   ├── system.py                      # health endpoint
│   │   ├── crawl.py, audit.py, content.py, diagnosis.py, intelligence.py
│   │   └── web.py
│   └── templates.py                       # Jinja2 environment
├── domain/
│   ├── models/
│   │   ├── search.py                      # SearchDataset, RankingObservation, etc.
│   │   ├── search_serp.py                 # SERPFeatureType, SearchSERPFeature
│   │   ├── search_aio.py                  # AI Overview models
│   │   ├── search_geo.py                  # GEO models
│   │   ├── search_performance.py          # Performance models
│   │   ├── search_entity.py               # Entity models
│   │   ├── search_optimization.py         # Optimization models
│   │   ├── search_report.py               # Report models
│   │   ├── search_analytics.py            # Analytics models
│   │   ├── industry.py                    # Industry/casino/crypto models
│   │   └── evidence.py                    # Evidence/Provenance models
│   ├── engines/                           # Pure deterministic analysis functions
│   ├── services/                          # Application-layer orchestration
│   ├── ports/                             # Protocol abstractions
│   └── renderers/pdf_renderer.py          # WeasyPrint PDF generation
├── infrastructure/
│   ├── search/                            # SearchProvider adapters
│   ├── persistence/                       # SQLAlchemy repositories
│   └── models/                            # ORM models
└── templates/                             # HTML templates (glassmorphism UI)
```

---

## Requirements

- Python >= 3.12
- SQLite (default) or PostgreSQL

### Core dependencies

```
fastapi, uvicorn, jinja2, httpx, beautifulsoup4, lxml,
pydantic, pydantic-settings, python-multipart,
sqlalchemy[asyncio], aiosqlite, alembic, rich
```

### Optional dependencies

```
weasyprint>=62    # Required for PDF report generation
```

---

## Installation

```bash
git clone <repo-url>
cd seo-intelligence-engine

python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# For PDF generation:
.venv/bin/pip install weasyprint

cp .env.example .env
# Edit .env with your configuration
```

---

## Running

```bash
# Start the application
.venv/bin/python -m sie

# Application available at:
#   UI:       http://127.0.0.1:8000
#   API docs: http://127.0.0.1:8000/docs
#   Health:   http://127.0.0.1:8000/health
```

---

## Environment Variables

All settings use `SIE_` prefix. Nested settings use `__` delimiter.

| Variable | Default | Description |
|----------|---------|-------------|
| `SIE_ENVIRONMENT` | `development` | `development`, `test`, or `production` |
| `SIE_DEBUG` | `true` | Enable debug mode |
| `SIE_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SIE_HOST` | `127.0.0.1` | Server bind address |
| `SIE_PORT` | `8000` | Server port |
| `SIE_DATABASE_URL` | `sqlite+aiosqlite:///./sie.db` | Database URL |
| `SIE_AUTO_MIGRATE` | `true` | Run migrations at startup |

### Search Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `SIE_SEARCH_PROVIDER__ENABLED` | `false` | Enable real search API |
| `SIE_SEARCH_PROVIDER__PROVIDER_NAME` | `mock` | `http` or `mock` |
| `SIE_SEARCH_PROVIDER__BASE_URL` | `""` | Base URL of search API |
| `SIE_SEARCH_PROVIDER__API_KEY` | `""` | API key for authentication |
| `SIE_SEARCH_PROVIDER__TIMEOUT_SECONDS` | `30` | Request timeout |

### LLM Provider (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `SIE_LLM__ENABLED` | `false` | Enable LLM-enhanced diagnosis |
| `SIE_LLM__BASE_URL` | `https://api.openai.com` | OpenAI-compatible API URL |
| `SIE_LLM__API_KEY` | `""` | API key |
| `SIE_LLM__MODEL` | `gpt-4o-mini` | Model name |

---

## Search Provider Configuration

### Architecture

```
SearchProviderSettings (env vars)
    ↓
Provider Factory (provider_factory.py)
    ↓
HttpSearchProvider (infrastructure/search/)
    ↓
External POST /search API
```

### When `SIE_SEARCH_PROVIDER__ENABLED=false`

The application uses `MockSearchProvider` (no network I/O). This is for development and testing only. The dashboard and health endpoint clearly indicate "Mock mode".

**There is no silent fallback from a failed real provider to mock data.**

### When `SIE_SEARCH_PROVIDER__ENABLED=true`

The application requires a configured HTTP search provider. If `BASE_URL` is missing, the application fails on startup with:

```
SearchProviderConfigError: Search provider 'http' requires SIE_SEARCH_PROVIDER__BASE_URL
```

### Expected External API Contract

**Request:**

```
POST {base_url}/search
Content-Type: application/json
Authorization: Bearer {api_key}   (when api_key is set)

{
    "query": "best crm software",
    "country": "us",
    "language": "en",
    "device": "desktop",
    "search_engine": "google",
    "target_domain": "example.com",   // omitted when None
    "max_results": 10
}
```

**Response (200 OK):**

```json
{
    "results": [
        {"title": "Example CRM", "url": "https://example.com/crm", "position": 1},
        {"title": "Other CRM", "url": "https://other.com/crm", "position": 2}
    ]
}
```

**Error responses:**

| HTTP Status | Meaning | SIE Behavior |
|-------------|---------|--------------|
| 401/403 | Auth failure | Raises `SearchProviderAuthenticationError` |
| 429 | Rate limit | Raises `SearchProviderRateLimit` |
| 4xx/5xx | Server error | Raises `SearchProviderError` |
| Timeout | Slow response | Raises `SearchProviderTimeout` |
| Invalid JSON | Malformed response | Raises `SearchProviderError` |

**Never exposes API keys in error messages or logs.**

---

## UI Pages

The application starts in **dark/night mode** by default. A theme toggle (sun/moon icon) in the navigation bar switches between dark and light themes. The choice persists in `localStorage`.

| Page | URL | Functionality |
|------|-----|---------------|
| **Dashboard** | `/` | Overview: dataset count, keyword count, provider status, system status, recent datasets |
| **Live Search** | `/search` | Execute real SERP queries: enter keyword + domain, collect rankings, view results |
| **Datasets** | `/datasets` | List all datasets, delete, import data |
| **Dataset Detail** | `/datasets/{id}` | View observations, keyword rankings, competitor analysis, run intelligence |
| **Intelligence** | `/intelligence` | Run search intelligence analysis on a dataset: recommendations, cannibalization, volatility |
| **Industry** | `/industry` | Run industry-specific intelligence: casino, crypto, crypto-casino, general |
| **Reports** | `/reports` | Download PDF reports, check report availability |
| **API Docs** | `/docs` | FastAPI auto-generated Swagger documentation |

### UI Features

- Glassmorphism design with translucent panels and backdrop blur
- Dark mode default with light mode toggle
- Responsive layout (desktop, tablet, mobile)
- Real-time API data consumption (no hard-coded values)
- Loading states, empty states, error states
- Severity-coded findings (red/amber/green)
- Evidence source tags on findings
- Confirmation dialogs before destructive actions

---

## Dataset Workflow

1. **Import data** via CSV (`POST /api/search/import/csv`) or JSON (`POST /api/search/import/json`)
2. **Or search live** via the `/search` page which creates a dataset and collects rankings
3. **View dataset** at `/datasets/{id}` — see observations, keywords, competitors
4. **Run analytics** — automatic ranking analytics on dataset view
5. **Run intelligence** — go to `/intelligence` for comprehensive analysis
6. **Generate report** — download PDF at `/reports`

---

## Intelligence Workflow

```
Dataset with observations + competitor rankings
    ↓
Search Intelligence Service
    ↓
┌─────────────────────────────────────┐
│ Cannibalization Detection           │
│ Ranking Volatility Analysis         │
│ Search Opportunity Detection        │
│ SERP Feature Analysis               │
│ AIO Intelligence                    │
│ GEO Intelligence                    │
│ Performance Analysis                │
│ Entity Analysis                     │
│ Optimization Synthesis              │
└─────────────────────────────────────┘
    ↓
Prioritized recommendations
    ↓
UI display / PDF report
```

---

## Industry Intelligence

Industry intelligence combines search data with industry-specific entity analysis.

**Supported industry types:** `general`, `casino`, `crypto`, `crypto_casino`

Each industry type has dedicated entity detection, topic analysis, and opportunity identification engines.

**Endpoint:** `POST /api/search-intelligence/industry/analyze`

**Evidence provenance:** Every finding and opportunity includes `evidence_sources` — a tuple of data source identifiers indicating which analysis produced the finding.

---

## Evidence / Provenance

The `Evidence` model provides a provenance chain:

```
Observed Data → Evidence → Source/Authority → Finding → Recommendation
```

- `EvidenceType`: observed, authoritative, analytical, derived
- `SourceType`: internal, external, google, bing, content, user_data
- `confidence`: 0.0–1.0 (1.0 = deterministic)
- `engine`: which engine produced the evidence

Evidence sources are:
1. Generated by synthesis engines during analysis
2. Persisted in the database as JSON
3. Restored on retrieval
4. Displayed in the UI as tags
5. Included in PDF reports

---

## Report / PDF Generation

**Endpoint:** `GET /api/reports/{report_id}/pdf`

**Requirements:** `weasyprint>=62` must be installed.

**Report contents:**
- Professional title page with report ID and generation timestamp
- Executive summary
- Severity-coded findings (high/medium/low) with evidence sources
- Recommendations table with priority scores
- Report metadata
- Page headers, footers, and page numbers

**If WeasyPrint is not installed**, the endpoint returns a clear error message indicating the missing dependency.

---

## Testing

```bash
# Run all tests (network tests excluded by default)
.venv/bin/python -m pytest

# Run specific test groups
.venv/bin/python -m pytest tests/unit/test_search_provider_factory.py -v
.venv/bin/python -m pytest tests/unit/test_web_routes.py -v
.venv/bin/python -m pytest tests/intelligence/ -v

# Include network tests (requires real API credentials)
.venv/bin/python -m pytest -m network
```

### Ruff

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/ruff format .    # auto-fix formatting
```

---

## Production Configuration

```bash
SIE_ENVIRONMENT=production
SIE_DEBUG=false
SIE_LOG_LEVEL=WARNING
SIE_DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
SIE_AUTO_MIGRATE=false    # run migrations separately in production

# Real search provider
SIE_SEARCH_PROVIDER__ENABLED=true
SIE_SEARCH_PROVIDER__PROVIDER_NAME=http
SIE_SEARCH_PROVIDER__BASE_URL=https://your-serp-api.com
SIE_SEARCH_PROVIDER__API_KEY=your-key-here
SIE_SEARCH_PROVIDER__TIMEOUT_SECONDS=30
```

**Production checklist:**
- [ ] Real search API credentials configured
- [ ] Database URL points to production database
- [ ] Migrations run separately (`alembic upgrade head`)
- [ ] `auto_migrate=false`
- [ ] WeasyPrint installed for PDF generation
- [ ] Reverse proxy (nginx/Caddy) for HTTPS
- [ ] `debug=false`

---

## Mock / Test Provider Behavior

| Scenario | Provider Used | Dashboard Shows |
|----------|---------------|-----------------|
| `ENABLED=false` | `MockSearchProvider` | "Mock mode" |
| `ENABLED=true, valid config` | `HttpSearchProvider` | "Enabled" |
| `ENABLED=true, missing URL` | **Fails on startup** | N/A |
| `ENABLED=true, bad API key` | `HttpSearchProvider` | "Enabled" (fails at request time) |

`MockSearchProvider` is used **only** when the provider is explicitly disabled. It is never used as a fallback for a misconfigured or failing real provider.

---

## Limitations

1. **External search API required** — Real SERP data requires a configured external API. The application cannot perform real searches without credentials.
2. **PDF requires WeasyPrint** — PDF generation depends on `weasyprint>=62` which requires system-level C libraries (pango, cairo, gdk-pixbuf).
3. **SQLite default** — Default database is SQLite. Production should use PostgreSQL.
4. **No authentication** — The UI and API have no user authentication.
5. **No rate limiting** — No API rate limiting is implemented.
6. **No HTTPS** — Application serves HTTP. Use a reverse proxy for production.

---

## Manual End-to-End Test

```bash
# 1. Start the application
.venv/bin/python -m sie

# 2. Open http://127.0.0.1:8000
#    - Verify dark mode dashboard loads
#    - Verify system status shows "Mock mode"

# 3. Toggle theme (sun/moon icon in nav)
#    - Verify light mode renders correctly
#    - Verify choice persists after page reload

# 4. Navigate to /search
#    - Enter keyword: "test query"
#    - Enter domain: "example.com"
#    - Click Search
#    - Verify dataset is created

# 5. Navigate to /datasets
#    - Verify new dataset appears
#    - Click View on the dataset

# 6. Navigate to /intelligence
#    - Enter the dataset ID
#    - Click Analyze
#    - Verify recommendations appear

# 7. Navigate to /reports
#    - Enter the dataset ID
#    - Click Download PDF
#    - Verify PDF downloads (requires WeasyPrint)

# 8. Check health endpoint
curl http://127.0.0.1:8000/health | python -m json.tool

# For real SERP testing:
# 1. Set environment variables:
export SIE_SEARCH_PROVIDER__ENABLED=true
export SIE_SEARCH_PROVIDER__PROVIDER_NAME=http
export SIE_SEARCH_PROVIDER__BASE_URL=https://your-serp-api.com
export SIE_SEARCH_PROVIDER__API_KEY=your-key

# 2. Restart the application
# 3. Dashboard should show "Enabled" for search provider
# 4. /search page should return real results
```
