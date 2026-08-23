# SEO Intelligence Engine

A zero-paid-API website intelligence and optimization platform: technical SEO auditing,
site architecture, content intelligence, AIO (AI Optimization) and GEO (Generative Engine
Optimization) readiness — built in Python.

Core data collection and all deterministic analysis are **LLM-free by design**.
LLMs may only ever be optional adapters behind ports, used for semantic layers on top of
deterministic foundations.

---

## Principles

- Modular, SOLID, clean separation of concerns (hexagonal-lite layering)
- Provider-independent: every external capability sits behind a `typing.Protocol`
- Deterministic engines never depend on LLM providers; dependencies point inward
- No paid APIs; polite crawling (robots.txt, pacing, scope)
- Configuration via environment (`.env`); nothing hardcoded
- Small files, no premature features, tests for everything that exists

## Architecture

```
┌──────────────────────────────────────────────────────┐
│ Interface       FastAPI app, routes, Jinja2/HTMX     │
├──────────────────────────────────────────────────────┤
│ Application     use cases / service orchestration    │
│                 (CrawlService, future analysis)      │
├──────────────────────────────────────────────────────┤
│ Domain          immutable models, ports (Protocols), │
│                 errors — zero third-party imports    │
├──────────────────────────────────────────────────────┤
│ Infrastructure  httpx fetcher, crawler engine,       │
│                 SQLAlchemy/SQLite, Alembic           │
└──────────────────────────────────────────────────────┘
```

## Crawler Engine

### What it does

Starts from a **seed URL**, crawls every linked page on the same domain (BFS), stores
each page in the database and returns real-time statistics as it runs.

**Built-in features:**

| Feature | Detail |
|---|---|
| BFS frontier | breadth-first traversal, depth-limited, page-capped |
| URL normalization | fragments stripped, scheme/host lowered, default ports dropped, query sorted |
| LRU deduplication | bounded visited-set prevents re-crawling (capacity configurable) |
| robots.txt | `urllib.robotparser`-based; conservative disallow on 5xx / transport failures |
| Per-host rate limiting | configurable requests-per-second per host (default 1 req/s) |
| Concurrency cap | `asyncio.Semaphore`-controlled parallel fetches (default 10) |
| Retry with backoff | exponential backoff + jitter on HTTP 429/503 and transport errors; honours `Retry-After` |
| Cross-origin gating | same-host enforcement by default; opt-in to follow external links |
| Provenance tracking | every stored page records `depth` and `parent_url` for link-graph builds |

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/crawl` | Start a new crawl (returns `run_id` + 202) |
| `GET` | `/api/crawl/{run_id}` | Crawl status, stats and error info |
| `GET` | `/api/crawl/{run_id}/pages` | Paginated fetched pages (`?limit=&offset=`) |
| `DELETE` | `/api/crawl/{run_id}` | Abort a running crawl (cooperative) |
| `GET` | `/api/crawl/history` | List all crawl runs (newest first) |
| `GET` | `/health` | Service health + database check |
| `GET` | `/docs` | Swagger interactive API docs (dev only) |

### Example crawl

```bash
# Start a crawl
curl -X POST http://localhost:8000/api/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com", "max_pages": 50, "depth_limit": 3}'

# Poll status
curl http://localhost:8000/api/crawl/<run_id>

# Fetch results
curl 'http://localhost:8000/api/crawl/<run_id>/pages?limit=50'

# View history
curl http://localhost:8000/api/crawl/history
```

## Project layout

```
src/sie/
├── __init__.py / __main__.py          # package version, entry point
├── config.py                          # pydantic-settings (SIE_ prefix)
├── logging.py                         # Rich logging bootstrap
├── api/
│   ├── app.py                         # create_app() composition root
│   ├── routes/{crawl,system,web}.py   # HTTP routes
│   └── templates.py                   # Jinja2 environment
├── domain/
│   ├── errors.py                      # domain error hierarchy
│   ├── models/{crawl,events,page}.py  # immutable value objects
│   ├── ports/{crawling,fetching,
│   │         persistence,rendering}.py # Protocol contracts
│   └── services/crawl_service.py      # run lifecycle orchestration
├── infrastructure/
│   ├── crawling/{engine,robots,
│   │           throttle,frontier,urls}.py  # BFS engine internals
│   ├── fetching/{httpx,retrying}.py   # fetcher implementations
│   ├── models/crawl_orm.py            # SQLAlchemy ORM
│   └── persistence/{database,repositories,migrations}.py
└── templates/index.html               # minimal healthcheck page

migrations/
├── env.py                             # sync Alembic runner
├── script.py.mako                     # revision template
└── versions/
    ├── 0001_create_crawl_tables.py
    └── 0002_add_provenance_and_run_summary.py
```

## Getting started

Requires Python ≥ 3.12.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

cp .env.example .env          # optional; defaults work out of the box
```

### Run the application

```bash
.venv/bin/python -m sie       # http://127.0.0.1:8000  · /docs  · /health
```

### Run tests & lint

```bash
.venv/bin/python -m pytest           # unit + integration (network tests excluded)
.venv/bin/python -m pytest -m network  # include real-network tests (power.win etc.)
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

### Manual migrations (when auto_migrate is off)

```bash
.venv/bin/alembic upgrade head
```

### Configuration

All settings are sourced from the environment with an `SIE_` prefix (see `.env.example`).
Nested crawler settings use `__`, e.g.:

```bash
SIE_CRAWLER__MAX_PAGES=500 SIE_LOG_LEVEL=DEBUG .venv/bin/python -m sie
```

## Roadmap

1. **Crawler Engine** — ✅ Done.
2. **Technical SEO Engine** — deterministic checks on crawled pages (titles, meta, headings, canonicals, status handling, redirect chains).
3. **Site Architecture / Internal Link Engines** — link graph construction and analysis.
4. **Content Intelligence & Schema Engines** — BeautifulSoup/lxml parsing layers.
5. **Performance, Entity, AIO/GEO, Competitor Gap, Diagnosis, Optimization,
   Reporting engines** — each a separate package exposing pure analysis functions over
   domain inputs; LLM-assisted engines arrive last, behind their own port.
