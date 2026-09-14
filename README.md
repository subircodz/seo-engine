# SEO - AIO - GEO Intelligence Engine

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: Deployment Ready](https://img.shields.io/badge/Status-Deployment_Ready-green.svg)]()

---

## 🌟 What Is This?

**SEO Intelligence Engine** is a self-hosted platform for technical SEO, search-ranking intelligence, AI Overview (AIO), and Generative Engine Optimization (GEO) analysis.

It collects search and site data, stores evidence, runs deterministic analysis, and presents findings through a web UI and professional PDF reports. LLM-based enhancement is optional; core analysis does not require an LLM.

### Core capabilities

- Live search and ranking collection through configurable providers
- Technical SEO and site analysis
- Content-quality and site-architecture analysis
- Cannibalization, volatility, opportunity, and SERP-feature analysis
- AIO/GEO visibility analysis
- Country-wise ranking analysis
- Industry-specific intelligence
- Evidence-backed findings and prioritized recommendations
- Web UI and PDF reporting
- SQLite for development and PostgreSQL for production
- Durable background jobs with database-backed ownership/leases
- SSRF, redirect, DNS, response-size, and request-limit guardrails

---

## 🏗️ Architecture

```text
                         ┌─────────────────────┐
                         │      Web / API      │
                         └──────────┬──────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
          Search Providers      Site Crawler       Analysis Engines
                │                   │                   │
                └───────────────────┼───────────────────┘
                                    ▼
                              PostgreSQL / SQLite
                                    │
                                    ▼
                           Reports / Web UI / API
```

### Design principles

1. **Domain-first** — business logic is separated from infrastructure.
2. **Protocol-based** — external providers can be replaced without rewriting the domain layer.
3. **Deterministic by default** — core intelligence is reproducible and does not require an LLM.
4. **Evidence-backed** — findings retain their supporting data.
5. **Fail closed in production** — unsafe production configuration is rejected at startup.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- A search-provider API key for real search data
- WeasyPrint system dependencies if PDF generation is required

### Install

```bash
git clone https://github.com/subircodz/seo-engine.git
cd seo-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,weasyprint]'
cp .env.example .env
```

Configure the provider in `.env`, then run:

```bash
python -m sie
```

Open `http://127.0.0.1:8000`.

---

## ⚙️ Configuration

All runtime configuration uses the `SIE_` prefix. Nested settings use `__`.

Examples:

```bash
SIE_ENVIRONMENT=development
SIE_DATABASE_URL=sqlite+aiosqlite:///./sie.db
SIE_SEARCH_PROVIDER__ENABLED=true
SIE_SEARCH_PROVIDER__PROVIDER_NAME=serpapi
SIE_SEARCH_PROVIDER__API_KEY=your-key
```

Production configuration uses `.env.production`. Never commit real credentials.

Production enforces these guardrails:

- `SIE_DEBUG=false`
- `SIE_DATABASE__AUTO_MIGRATE=false`
- `SIE_HOST` cannot be localhost-only
- enabled API authentication requires at least one API key

---

## 🐳 Production Deployment

The repository includes a production Dockerfile and Compose deployment.

### Production checklist

- [ ] PostgreSQL credentials configured
- [ ] `SIE_DATABASE_URL` points to the PostgreSQL service and uses the URL-encoded password
- [ ] `SIE_ENVIRONMENT=production`
- [ ] `SIE_DEBUG=false`
- [ ] `SIE_DATABASE__AUTO_MIGRATE=false`
- [ ] Real provider credentials configured
- [ ] Long random API key configured when direct API authentication is enabled
- [ ] HTTPS reverse proxy/load balancer configured
- [ ] Database backups configured and restore-tested
- [ ] Port 8000 is not publicly exposed

### Docker Compose

```bash
cp .env.production.example .env.production
chmod 600 .env.production
# Replace every CHANGE_ME value and keep SIE_DATABASE_URL in sync with the
# PostgreSQL credentials. URL-encode special characters in its password.
docker compose -f docker-compose.production.yml up -d db
docker compose -f docker-compose.production.yml run --rm app alembic upgrade head
docker compose -f docker-compose.production.yml up -d app
```

Verify:

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
```

For the complete deployment procedure, backups, HTTPS requirements, update procedure, and scaling constraint, see [`docs/PRODUCTION.md`](docs/PRODUCTION.md).

**Important:** the current durable job worker runs inside the application process. Keep one Uvicorn worker until job execution is separated into a dedicated worker service.

---

## 🔧 Development

### Project structure

```text
src/sie/
├── api/             # FastAPI app, routes, templates
├── domain/          # Business logic and domain models
├── infrastructure/ # Database, HTTP, and provider adapters
└── templates/       # Web templates
```

### Tests and quality checks

```bash
pytest
ruff check .
ruff format .
alembic upgrade head
alembic check
```

CI validates Python 3.12 and 3.13, compilation, Ruff, tests, Alembic migrations, production Compose configuration, and the production container build.

---

## 🔐 Security Notes

The crawler applies SSRF and redirect protections, robots-policy handling, request limits, and a hard response-size ceiling. Production configuration also fails fast on unsafe local defaults.

DNS validation is performed before outbound requests, but the current HTTP client architecture does **not** claim complete DNS-rebinding/TOCTOU protection.

Durable job leases prevent stale workers from overwriting active ownership, but a process crash can still result in duplicate execution after lease expiry. The queue therefore provides **at-least-once**, not exactly-once, execution semantics.

Report security vulnerabilities privately rather than posting exploit details in a public issue.

---

## 📦 Dependencies

Core runtime dependencies include FastAPI, Uvicorn, HTTPX, BeautifulSoup, lxml, Pydantic, SQLAlchemy, Alembic, Redis support, and Rich. WeasyPrint is optional for PDF generation.

---

## 📜 License

**Apache License 2.0**. See [`LICENSE`](LICENSE) for the complete license text.

---

## 📊 Status

| Component | Status |
|-----------|--------|
| Core Intelligence | ✅ Ready |
| Web UI | ✅ Ready |
| PDF Reports | ✅ Ready |
| Search Provider Integration | ✅ Ready |
| Industry Intelligence | ✅ Ready |
| AIO/GEO Analysis | ✅ Ready |
| Production Container | ✅ Validated by CI |
| Production Deployment | ⏳ Requires hosting/secrets/domain setup |

---

**Made with ❤️ for the SEO community.**
