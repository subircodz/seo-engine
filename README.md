# SEO Intelligence Engine - SEO, AEO & GEO Intelligence Platform

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: Validated](https://img.shields.io/badge/Status-Validated-green.svg)]()

**SEO Intelligence Engine** is a self-hosted, evidence-backed **SEO, Answer Engine Optimization (AEO), and Generative Engine Optimization (GEO) platform** for technical SEO audits, website crawling, search intelligence, competitor analysis, AI-search visibility, entity analysis, and actionable optimization recommendations.

Instead of turning a website into a black-box LLM prompt, SEO Intelligence Engine collects measurable site and search evidence, analyzes it through deterministic workflows, and turns that evidence into findings, opportunities, recommendations, and reports.

> **The idea is simple:** understand what is happening across your search visibility, not just what a language model thinks might be happening.

---

<img width="996" height="209" alt="SEO Intelligence Engine" src="https://github.com/user-attachments/assets/08eb05ab-d208-41c2-b7e0-3430a9a83bd6" />

## Why SEO Intelligence Engine?

Search visibility is no longer only about traditional rankings.

A modern SEO workflow can involve:

- Technical SEO and crawl health
- On-page and content quality
- Internal linking and site architecture
- Keywords, rankings, and SERP features
- Competitor search visibility
- Entities and topical signals
- Answer Engine Optimization (AEO)
- Google AI Overview and AI-answer observations
- Generative Engine Optimization (GEO)
- Evidence-backed recommendations

SEO Intelligence Engine brings these areas into one self-hosted analysis workflow.

The goal is not to generate impressive-sounding SEO advice. The goal is to produce **traceable findings backed by the data collected during analysis**.

## What It Analyzes

| Area | What you get |
|---|---|
| **Technical SEO** | Crawl-based technical checks, response and redirect signals, robots handling, and site-level findings |
| **On-page SEO** | Page-level content and SEO analysis |
| **Site architecture** | Internal links and architecture signals |
| **Search intelligence** | Keyword and ranking collection, cannibalization, volatility, opportunities, and SERP features |
| **Competitor SEO** | Country-aware ranking analysis and competitor comparison |
| **Entity SEO** | Entity extraction and entity-related analysis |
| **AEO** | Provider-backed Answer Engine Optimization and AI-answer visibility analysis |
| **GEO** | Provider and LLM-backed Generative Engine Optimization analysis |
| **Performance** | Page and resource performance signals used by the analysis workflow |
| **Recommendations** | Evidence-backed findings and prioritized optimization recommendations |
| **Reporting** | Web UI, HTTP API, and PDF reports |

## Built for Real SEO Investigation

A useful SEO platform should help answer questions such as:

- Why is this page underperforming?
- Which technical problems are affecting crawlability or discoverability?
- Which keywords and SERP opportunities deserve attention?
- Where is keyword cannibalization happening?
- How does a competitor compare across search visibility?
- Which entities and site-architecture signals need attention?
- Is a site appearing in provider-backed AI answers?
- What evidence supports an AEO or GEO finding?
- What should be investigated or improved next?

The application is designed around those investigation workflows rather than a single generic "SEO score".

---

## SEO + AEO + GEO: One Search Visibility Model

SEO, AEO, and GEO overlap, but they are not the same thing.

- **SEO - Search Engine Optimization:** technical health, content, links, rankings, SERP features, entities, and site architecture.
- **AEO - Answer Engine Optimization:** visibility in answer-oriented search experiences, including provider-backed AI Overview and AI-answer observations.
- **GEO - Generative Engine Optimization:** visibility and representation in generative and LLM-backed search experiences using compatible providers and collected evidence.

A strong traditional ranking does not automatically prove visibility inside an AI-generated answer. SEO Intelligence Engine therefore keeps these signals distinct while bringing them together in the same analysis workflow.

```text
                         Site + Search Inputs
                                  |
              +-------------------+-------------------+
              |                   |                   |
              v                   v                   v
        Technical SEO       Search / SERP       AEO / GEO Signals
        Content / Links      Rankings            Provider-backed
              |                   |                   |
              +-------------------+-------------------+
                                  |
                                  v
                         Evidence + Analysis
                                  |
                 +----------------+----------------+
                 |                |                |
                 v                v                v
             Findings       Opportunities     Recommendations
                 |                |                |
                 +----------------+----------------+
                                  |
                                  v
                          Web / API / PDF
```

## Evidence-Backed by Design

The project is deliberately different from an "ask an LLM to audit my website" tool.

Core SEO analysis is designed to work without an LLM. Provider-backed AEO and GEO analysis is used where compatible external data is available.

That means the system can separate:

1. **What was observed**
2. **What the analysis derived from the observation**
3. **What recommendation follows from that evidence**

This makes results easier to inspect, test, reproduce, and challenge.

> **Scope note:** AEO/GEO coverage depends on configured providers and available input data. The project does not claim universal access to every search engine, AI answer surface, model, or external data source.

---

## Architecture

```text
                         +---------------------+
                         |      Web / API      |
                         +----------+----------+
                                    |
                +-------------------+-------------------+
                |                   |                   |
                v                   v                   v
          Search Providers      Site Crawler       Analysis Engines
                |                   |                   |
                +-------------------+-------------------+
                                    |
                                    v
                              PostgreSQL / SQLite
                                    |
                                    v
                           Reports / Web UI / API
```

### Design principles

1. **Domain-first** - business logic is separated from infrastructure.
2. **Protocol-based** - external providers can be replaced without rewriting the domain layer.
3. **Deterministic where applicable** - core site and SEO analysis does not require an LLM.
4. **Evidence-backed** - findings retain supporting data used by the analysis workflow.
5. **Fail closed in production** - unsafe production configuration is rejected at startup.
6. **Testable** - application behavior is covered through unit, API, integration, and infrastructure-oriented tests.

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

Configure the required providers in .env, then run:

```bash
python -m sie
```

Open http://127.0.0.1:8000.

### Health checks

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
```

---

## Configuration

Runtime configuration uses the SIE_ prefix. Nested settings use __.

Example:

```bash
SIE_ENVIRONMENT=development
SIE_DATABASE_URL=sqlite+aiosqlite:///./sie.db
SIE_SEARCH_PROVIDER__ENABLED=true
SIE_SEARCH_PROVIDER__PROVIDER_NAME=serpapi
SIE_SEARCH_PROVIDER__API_KEY=your-key
```

Production configuration uses .env.production. Never commit real credentials.

Production guardrails include:

- SIE_DEBUG=false
- SIE_DATABASE__AUTO_MIGRATE=false
- SIE_HOST cannot be localhost-only
- enabled API authentication requires at least one API key

---

## Production Deployment

The repository includes a production Dockerfile and Compose deployment configuration.

This project is **self-hosted**, not a hosted SEO SaaS. Operators are responsible for hosting, secrets, HTTPS termination, backups, monitoring, and database operations.

### Production checklist

- [ ] PostgreSQL credentials configured
- [ ] SIE_DATABASE_URL points to the PostgreSQL service and uses the URL-encoded password
- [ ] SIE_ENVIRONMENT=production
- [ ] SIE_DEBUG=false
- [ ] SIE_DATABASE__AUTO_MIGRATE=false
- [ ] Real provider credentials configured
- [ ] Long random API key configured when direct API authentication is enabled
- [ ] HTTPS reverse proxy or load balancer configured
- [ ] Database backups configured and restore-tested
- [ ] Port 8000 is not publicly exposed

### Docker Compose

```bash
cp .env.production.example .env.production
chmod 600 .env.production
# Replace every CHANGE_ME value and keep SIE_DATABASE_URL in sync
# with the PostgreSQL credentials. URL-encode special characters
# in the database password.
docker compose -f docker-compose.production.yml up -d db
docker compose -f docker-compose.production.yml run --rm app alembic upgrade head
docker compose -f docker-compose.production.yml up -d app
```

Verify:

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
```

For the complete deployment procedure, backups, HTTPS requirements, update procedure, and scaling constraint, see [docs/PRODUCTION.md](docs/PRODUCTION.md).

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

DNS validation is performed before outbound requests, but the current HTTP client architecture does **not** claim complete DNS-rebinding or TOCTOU protection.

Durable job leases prevent stale workers from overwriting active ownership, but a process crash can still result in duplicate execution after lease expiry. The queue therefore provides **at-least-once**, not exactly-once, execution semantics.

See [SECURITY.md](SECURITY.md) for private vulnerability reporting instructions. Security vulnerabilities should **not** be reported through public issues, discussions, or pull requests.

---

## Who Is It For?

SEO Intelligence Engine is intended for:

- SEO engineers
- Technical SEO teams
- Developers building SEO automation
- Agencies performing technical and competitor SEO research
- Search-intelligence researchers
- Teams experimenting with AEO and GEO workflows
- Engineers who want a self-hosted alternative to opaque SEO analysis workflows

It is especially useful when you want to inspect the evidence behind an SEO finding instead of accepting a generated score at face value.

---

## Frequently Asked Questions

### What is an SEO Intelligence Engine?

It is a self-hosted application for analyzing technical SEO, content, site architecture, search rankings, SERP signals, entities, competitors, and related search-visibility evidence.

### What is AEO?

**AEO means Answer Engine Optimization.** In this project, AEO covers provider-backed analysis of visibility in answer-oriented search experiences, including available AI Overview and AI-answer observations.

### Does it analyze Google AI Overview?

It supports provider-backed AEO visibility analysis when a compatible provider is configured and the required input data is available. It does not claim universal access to every Google AI Overview result.

### What is GEO?

**GEO means Generative Engine Optimization.** It covers analysis of visibility and representation in generative AI and LLM-backed search experiences using compatible providers and collected evidence.

### Is an LLM required for SEO analysis?

No. Core site and SEO analysis is designed to operate without an LLM. AEO and GEO capabilities may require compatible external providers.

### Can it analyze competitors?

Yes. The application includes competitor ranking comparison and related search-intelligence capabilities when configured providers supply the required data.

### Is this a hosted SEO SaaS?

No. SEO Intelligence Engine is a self-hosted application. Hosting, credentials, HTTPS, backups, monitoring, and external provider accounts remain the operator's responsibility.

### Can I use it as an SEO crawler?

Yes. The crawler supports technical site analysis and feeds collected evidence into the broader SEO intelligence workflow.

---

## Dependencies

Core runtime dependencies include FastAPI, Uvicorn, HTTPX, BeautifulSoup, lxml, Pydantic, SQLAlchemy, Alembic, Redis support, and Rich. WeasyPrint is optional for PDF generation.

---

## Contributing

Contributions are welcome, especially feature development, bug fixes, tests, documentation, and engineering improvements.

- Use GitHub issues and discussions for feature ideas, questions, design discussions, and development conversations.
- Pull requests are welcome for normal feature and development work.
- **Do not submit security vulnerabilities as public issues, discussions, or pull requests.** Follow [SECURITY.md](SECURITY.md) instead.
- For substantial feature development, opening an issue or discussion before implementation is encouraged so the direction can be agreed on early.

---

## Project Status

The application and its production-oriented CI checks are validated on Python 3.12 and 3.13.

The project is actively developed for self-hosted SEO intelligence, search visibility analysis, AEO/GEO experimentation, and evidence-backed optimization workflows.

The repository is suitable for further development and self-hosted deployment, subject to completing the production checklist and configuring the required external providers.

---

## License

**Apache License 2.0**. See [LICENSE](LICENSE) for the complete license text.

---

**Made with ❤️ for the SEO community.**