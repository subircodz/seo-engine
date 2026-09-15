# SEO - AIO - GEO Intelligence Engine

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: Validated](https://img.shields.io/badge/Status-Validated-green.svg)]()

---

## What Is This?

**SEO Intelligence Engine** is a self-hosted application for technical SEO, search-ranking intelligence, AI Overview (AIO), and Generative Engine Optimization (GEO) analysis.

It collects site and search data, stores evidence, runs analysis engines, and presents findings through a web UI, API, and PDF reports. LLM-based analysis is optional for the core SEO workflow; AIO/GEO provider-backed analysis requires the corresponding provider configuration.

### Current capabilities

- Site crawling with request, redirect, response-size, robots, and SSRF guardrails
- Technical SEO analysis
- Content-quality analysis
- Site-architecture and link analysis
- Keyword and search-ranking collection through configurable providers
- Search-intelligence analysis including cannibalization, volatility, opportunities, and SERP features
- Entity analysis
- Country-wise ranking analysis
- Competitor ranking comparison
- Industry-specific intelligence
- AIO visibility analysis when a compatible provider is configured
- GEO visibility analysis when a compatible LLM/provider is configured
- Evidence-backed findings and prioritized recommendations
- Web UI, HTTP API, and PDF reporting
- SQLite for development and PostgreSQL for production
- Durable database-backed background jobs with at-least-once execution semantics

The application is designed to produce analysis from real site/search inputs. Provider-dependent features require valid provider configuration and suitable input data; this repository does not claim universal coverage of every search engine, AI answer surface, or external data source.

---

## Architecture

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
3. **Deterministic where applicable** — core site and SEO analysis does not require an LLM.
4. **Evidence-backed** — findings retain supporting data used by the analysis workflow.
5. **Fail closed in production** — unsafe production configuration is rejected at startup.

---

## Quick Start

### Prerequisites

- Python 3.12+
- A search-provider API key when real search data is required
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

Configure the required providers in `.env`, then run:

```bash
python -m sie
```

Open `http://127.0.0.1:8000`.

---

## Configuration

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

## Production Deployment

The repository includes a production Dockerfile and Compose deployment configuration.

A deployment is **not** provided as a hosted service by this repository. Operators are responsible for hosting, secrets, HTTPS termination, backups, monitoring, and database operations.

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

## Development

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

CI validates Python 3.12 and 3.13, compilation, Ruff, the test suite, Alembic migrations, production Compose configuration, and the production container build.

---

## Security

The crawler applies SSRF and redirect protections, robots-policy handling, request limits, and a hard response-size ceiling. Production configuration also fails fast on unsafe local defaults.

DNS validation is performed before outbound requests, but the current HTTP client architecture does **not** claim complete DNS-rebinding/TOCTOU protection.

Durable job leases prevent stale workers from overwriting active ownership, but a process crash can still result in duplicate execution after lease expiry. The queue therefore provides **at-least-once**, not exactly-once, execution semantics.

Please see [`SECURITY.md`](SECURITY.md) for private vulnerability reporting instructions. Security vulnerabilities should **not** be reported through public issues, discussions, or pull requests.

---

## Contributing

Contributions are welcome, especially feature development, bug fixes, tests, documentation, and engineering improvements.

- Use GitHub issues and discussions for feature ideas, questions, design discussions, and general development conversations.
- Pull requests are welcome for normal feature and development work.
- **Do not submit security vulnerabilities as public issues, discussions, or pull requests.** Follow [`SECURITY.md`](SECURITY.md) and email `subirthecoder35@gmail.com` instead.
- For feature development or other project discussions, opening an issue or discussion before substantial work is encouraged so the direction can be agreed on early.

---

## Dependencies

Core runtime dependencies include FastAPI, Uvicorn, HTTPX, BeautifulSoup, lxml, Pydantic, SQLAlchemy, Alembic, Redis support, and Rich. WeasyPrint is optional for PDF generation.

---

## License

**Apache License 2.0**. See [`LICENSE`](LICENSE) for the complete license text.

---

## Project status

The application and its production-oriented CI checks are validated on Python 3.12 and 3.13. The repository is suitable for further development and self-hosted deployment, subject to the operator completing the production checklist and configuring the required external providers.

The project is actively open to feature development, engineering discussion, and contributions.

---

**Made with ❤️ for the SEO community.**
