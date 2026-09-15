# SEO Intelligence Engine — SEO, AIO & GEO

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: Validated](https://img.shields.io/badge/Status-Validated-green.svg)]()

**SEO Intelligence Engine** is a self-hosted, evidence-backed **SEO, AI Overview (AIO), and Generative Engine Optimization (GEO)** analysis platform. It combines technical SEO auditing, site crawling, search-ranking intelligence, SERP analysis, entity analysis, competitor comparison, AI-search visibility analysis, and prioritized optimization recommendations in one application.

It is designed for teams and engineers who want to investigate **search visibility across traditional search and AI answer surfaces** using collected site/search evidence rather than a purely LLM-generated audit.

> **Scope note:** Core SEO analysis is designed to work without an LLM. AIO/GEO analysis depends on compatible external providers and suitable input data. The project does not claim universal coverage of every search engine, AI answer surface, or external data source.

---

## What Does It Analyze?

| Area | What the application provides |
|---|---|
| **Technical SEO** | Crawl-based technical checks, response/redirect signals, robots handling, and site-level findings |
| **On-page / Content SEO** | Content-quality and page-level analysis |
| **Site architecture** | Internal-link and architecture analysis |
| **Search intelligence** | Keyword/ranking collection, cannibalization, volatility, opportunities, and SERP features |
| **Competitor SEO** | Country-wise ranking analysis and competitor ranking comparison |
| **Entity SEO** | Entity extraction and entity-related analysis |
| **AI Overview (AIO)** | Provider-backed visibility analysis when a compatible provider is configured |
| **Generative Engine Optimization (GEO)** | Provider/LLM-backed visibility analysis when compatible configuration and input data are available |
| **Performance** | Page/resource performance signals used by the analysis workflow |
| **Recommendations** | Evidence-backed findings and prioritized optimization recommendations |
| **Reporting** | Web UI, HTTP API, and PDF reports |

### Common use cases

- Technical SEO audits and site health investigations
- SEO crawler and website analysis workflows
- Search-ranking and SERP intelligence
- Keyword opportunity and cannibalization analysis
- Competitor SEO research
- AI Overview / Google AI Overview visibility research
- Generative Engine Optimization (GEO) and AI-search visibility research
- Entity and site-architecture analysis
- Evidence-backed SEO recommendations and reporting

---

## Why This Project?

Traditional SEO tools focus heavily on rankings and crawl data. Modern search visibility also includes **AI-generated answers, citations, entities, and generative search experiences**.

SEO Intelligence Engine brings these related signals into one analysis workflow:

```text
                         Site + Search Inputs
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
        Technical SEO       Search / SERP       AIO / GEO Signals
        Content / Links      Rankings            Provider-backed
              │                   │                   │
              └───────────────────┼───────────────────┘
                                  ▼
                         Evidence + Analysis
                                  │
                 ┌────────────────┼────────────────┐
                 ▼                ▼                ▼
             Findings       Opportunities     Recommendations
                 │                │                │
                 └────────────────┼────────────────┘
                                  ▼
                          Web / API / PDF
```

The core design goal is **evidence-backed search visibility analysis**, not an opaque “ask an LLM to audit my website” workflow.

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

## SEO, AIO and GEO Data Model

The project treats SEO, AIO, and GEO as related but distinct analysis areas:

- **SEO (Search Engine Optimization):** technical health, content, links, rankings, SERP features, entities, and site architecture.
- **AIO (AI Overview):** visibility in provider-backed AI Overview / AI answer observations, including evidence available from the configured provider.
- **GEO (Generative Engine Optimization):** analysis of visibility and representation in generative/LLM-backed search experiences using compatible providers and collected evidence.

This separation matters because **ranking in a traditional SERP does not automatically mean visibility in an AI-generated answer**. The application therefore keeps provider-backed AIO/GEO signals distinct from conventional SEO signals.

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

## Frequently Asked Questions

### What is an SEO Intelligence Engine?

It is a self-hosted application for analyzing technical SEO, content, site architecture, search rankings, SERP signals, entities, competitors, and related search-visibility evidence.

### Does it analyze Google AI Overviews (AIO)?

It supports provider-backed AIO visibility analysis when a compatible provider is configured and the required input data is available. It does not claim universal access to every Google AI Overview result.

### What is GEO in this project?

GEO means **Generative Engine Optimization**: analyzing and improving visibility or representation in generative AI and LLM-backed search experiences. GEO analysis in this project is provider-dependent rather than a promise of universal coverage across every AI system.

### Is an LLM required for SEO analysis?

No. The core site and SEO workflow is designed to operate without an LLM. AIO/GEO capabilities may require compatible external providers.

### Is this a hosted SEO SaaS?

No. This repository provides a self-hosted application. Hosting, credentials, HTTPS, backups, monitoring, and external provider accounts remain the operator's responsibility.

### Can I use it for competitor SEO analysis?

Yes, the application includes competitor ranking comparison and related search-intelligence capabilities when the configured providers supply the required data.

---

## License

**Apache License 2.0**. See [`LICENSE`](LICENSE) for the complete license text.

---

## Project status

The application and its production-oriented CI checks are validated on Python 3.12 and 3.13. The repository is suitable for further development and self-hosted deployment, subject to the operator completing the production checklist and configuring the required external providers.

The project is actively open to feature development, engineering discussion, and contributions.

---

**Made with ❤️ for the SEO community.**
