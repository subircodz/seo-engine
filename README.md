# SEO - AIO - GEO Intelligence Engine

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: Production Ready](https://img.shields.io/badge/Status-Production_Ready-green.svg)]()

---

## 🌟 What Is This?

**SEO Intelligence Engine** is a powerful, self-hosted platform that helps you understand how websites rank in search engines — and more importantly, *why* they rank the way they do.

Think of it as your personal SEO analyst that works 24/7. It:
- **Collects real search rankings** from Google, Bing, and other engines
- **Analyzes the data** to find problems and opportunities
- **Generates professional PDF reports** you can share with clients or your team
- **Runs completely on your own server** — your data never leaves your infrastructure

### Why Does It Exist?

Most SEO tools are either:
- **Too expensive** (hundreds of dollars per month)
- **Locked in the cloud** (your data belongs to someone else)
- **Black boxes** (you get scores but no explanation)

This engine gives you **full control**, **complete transparency**, and **zero recurring costs**. It's built for agencies, in-house teams, and consultants who want enterprise-grade intelligence without the enterprise price tag.

### Who Is This For?

| If you are... | This helps you... |
|---------------|-------------------|
| An SEO agency | Deliver deeper insights to clients, automate reporting |
| An in-house SEO | Track competitors, find content gaps, prioritize fixes |
| A consultant | Run audits faster, back recommendations with data |
| A developer | Build custom SEO tools on a solid foundation |

---

## ✨ What It Can Do

### 🔍 **Live Search & Ranking Collection**
Type a keyword and a domain — the engine fetches real-time rankings from search engines and shows exactly where that domain appears.

### 📊 **Search Analytics (The "What")**
- Position tracking over time
- Visibility scores (how much of the SERP you own)
- Keyword-level metrics: best/worst/average position
- Top 3, Top 10, Top 20 breakdowns

### 🧠 **Search Intelligence (The "Why" & "What Next")**
| Analysis | What It Finds |
|----------|---------------|
| **Cannibalization** | Multiple pages fighting for the same keyword |
| **Volatility** | Keywords where rankings jump around unpredictably |
| **Opportunities** | Competitor gaps, weak rankings you can improve, missing content |
| **SERP Features** | Featured snippets, local packs, "People Also Ask" you could own |
| **AI Overview (AIO)** | Whether AI-generated answers cite your site |
| **Generative Engine (GEO)** | How you appear in ChatGPT, Perplexity, and other AI search |

### 🏢 **Industry-Specific Intelligence**
Pre-built analysis for:
- **Casino & Gambling** — compliance, trust signals, bonus structures
- **Crypto & Web3** — technical trust, regulatory signals, community
- **Crypto-Casino** — intersection of both verticals
- **General** — any other industry

### 📄 **Professional PDF Reports**
One-click generation of polished reports with:
- Executive summary
- Severity-coded findings (🔴 High / 🟡 Medium / 🟢 Low)
- Prioritized recommendations with confidence scores
- Evidence trail for every claim
- Page headers, footers, and numbering

### 🎨 **Beautiful Web Interface**
- **Dark mode by default** (easy on the eyes)
- **Light mode toggle** (persists your preference)
- **Glassmorphism design** — modern, clean, responsive
- **7 pages**: Dashboard, Live Search, Datasets, Intelligence, Industry, Reports, API Docs

---

## 🏗️ How It Works (Simple Version)

```
┌────────────────────────────────────────────────────────────┐
│  YOU TYPE A KEYWORD + DOMAIN                                │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│  ENGINE QUERIES SEARCH API (SerpAPI, DataForSEO, etc.)     │
│  Gets back: position, URL, title for top 10-100 results    │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│  DATA SAVED TO YOUR DATABASE (SQLite or PostgreSQL)        │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│  ANALYSIS ENGINES RUN (100% deterministic, no AI needed)   │
│  • Math & algorithms find patterns                          │
│   Zero hallucination, zero API costs                        │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│  RESULTS → WEB UI OR PDF REPORT                             │
└────────────────────────────────────────────────────────────┘
```

### The "Secret Sauce": Deterministic Intelligence
Unlike tools that just call GPT and hope for the best, this engine uses **pure math and algorithms** for all core analysis:
- No AI required for rankings, cannibalization, volatility, opportunities
- **LLMs are optional** — only used for enhanced reasoning if *you* enable them
- Results are **reproducible, auditable, and free to run**

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- **Python 3.12+** (check with `python3 --version`)
- A **search API key** (free tiers available from [SerpAPI](https://serpapi.com), [DataForSEO](https://dataforseo.com), or [ValueSERP](https://valueserp.com))

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/seo-intelligence-engine.git
cd seo-intelligence-engine

# 2. Create a virtual environment (keeps things isolated)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install the engine
pip install -e '.[dev]'

# 4. Install PDF generation (optional but recommended)
pip install weasyprint

# 5. Copy the example config and edit it
cp .env.example .env
# Edit .env with your favorite editor (nano, vim, VS Code, etc.)
```

### Configure Your Search API (Required for Real Data)

Open `.env` and find these lines:

```bash
# Change false → true
SIE_SEARCH_PROVIDER__ENABLED=true

# Use SerpAPI (recommended for beginners)
SIE_SEARCH_PROVIDER__PROVIDER_NAME=serpapi

# Paste your API key here
SIE_SEARCH_PROVIDER__API_KEY=your-actual-api-key-here
```

> **Don't have an API key?** Get a free one from [SerpAPI](https://serpapi.com) (100 searches/month free). The engine also supports DataForSEO, ValueSERP, and custom HTTP providers.

### Run It

```bash
# Start the server
python -m sie
```

Open your browser to **http://127.0.0.1:8000** — you should see the dashboard!

---

## 📖 First-Time Walkthrough

### 1. **Dashboard** — Your Command Center
See dataset count, keyword count, search provider status, and recent activity at a glance.

### 2. **Live Search** — Get Real Data
- Enter a keyword (e.g., "best running shoes")
- Enter a domain (e.g., "nike.com" or "https://nike.com")
- Pick a country (US, UK, DE, etc.)
- Click **Search** → watch it collect real rankings

### 3. **Datasets** — Your Data Library
All searches are saved as datasets. Browse, delete, or dive deeper.

### 4. **Dataset Detail** — The Full Picture
Click any dataset to see:
- Every keyword and its ranking position
- Competitor rankings side-by-side
- Historical trends (as data accumulates)

### 5. **Intelligence** — The Magic Happens
- Pick a dataset from the dropdown
- Enter the target domain
- Click **Analyze** → get prioritized recommendations in seconds

### 6. **Reports** — Share the Insights
- Click **Download PDF** on any analyzed dataset
- Get a professional report ready for clients or stakeholders

---

## ⚙️ Configuration Guide (Plain English)

All settings live in the `.env` file. Here's what matters:

| Setting | What It Does | Example |
|---------|--------------|---------|
| `SIE_ENVIRONMENT` | `development` (verbose logs) or `production` (quiet) | `development` |
| `SIE_DATABASE_URL` | Where data lives. SQLite for dev, PostgreSQL for prod | `sqlite+aiosqlite:///./sie.db` |
| `SIE_SEARCH_PROVIDER__ENABLED` | **Must be `true` for real search data** | `true` |
| `SIE_SEARCH_PROVIDER__PROVIDER_NAME` | Which search API: `serpapi`, `http`, or `mock` | `serpapi` |
| `SIE_SEARCH_PROVIDER__API_KEY` | Your search API key | `abc123...` |
| `SIE_LLM__ENABLED` | Enable AI-enhanced analysis (optional) | `false` |
| `SIE_LLM__API_KEY` | OpenAI-compatible API key (if LLM enabled) | `sk-...` |

> **Tip:** The `.env.example` file has every possible setting with comments. Never commit your real `.env` to git!

---

## 🔧 For Developers

### Project Structure
```
src/sie/
├── api/           # FastAPI app, routes, templates
├── domain/        # Pure business logic (no external deps)
│   ├── models/    # Data structures
│   ├── engines/   # Analysis algorithms (pure functions)
│   ├── services/  # Orchestration layer
│   └── ports/     # Interfaces (protocols)
├── infrastructure/# Database, HTTP, search adapters
└── templates/     # HTML (Jinja2 + HTMX-ready)
```

### Key Design Principles
1. **Domain-first** — Business logic never imports infrastructure
2. **Protocol-based** — Swap databases, search providers, LLMs without touching domain code
3. **Deterministic by default** — Core intelligence uses 0 LLM calls
4. **Evidence-backed** — Every finding traces back to source data

### Running Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=src/sie

# Linting
ruff check .
ruff format .
```

### Adding a New Search Provider
1. Implement `SearchProvider` protocol in `infrastructure/search/`
2. Register it in `provider_factory.py`
3. Add config to `SearchProviderSettings` in `config.py`
4. Done — zero changes to domain or application code

---

## 📦 Dependencies

### Required
```
fastapi, uvicorn, jinja2, httpx, beautifulsoup4, lxml,
pydantic, pydantic-settings, python-multipart,
sqlalchemy[asyncio], aiosqlite, alembic, rich
```

### Optional
```
weasyprint>=62    # PDF reports (needs system libs: pango, cairo, gdk-pixbuf)
```

### System Requirements for WeasyPrint (PDF)
| OS | Command |
|----|---------|
| Ubuntu/Debian | `apt-get install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0` |
| macOS | `brew install pango cairo gdk-pixbuf` |
| Windows | Use conda or WSL |

---

## 🐳 Production Deployment

### Quick Checklist
- [ ] `SIE_ENVIRONMENT=production`
- [ ] `SIE_DEBUG=false`
- [ ] `SIE_DATABASE_URL=postgresql+asyncpg://...`
- [ ] `SIE_AUTO_MIGRATE=false` (run `alembic upgrade head` separately)
- [ ] Real search API credentials configured
- [ ] WeasyPrint installed for PDFs
- [ ] Reverse proxy (nginx/Caddy) with HTTPS
- [ ] Process manager (systemd, supervisor, or Docker)

### Docker (Recommended)
```dockerfile
# Dockerfile included in repo
docker build -t sie .
docker run -d -p 8000:8000 --env-file .env sie
```

---

## 📜 License

**Apache License 2.0** — See [LICENSE](LICENSE) for full text.

**TL;DR:** You can use, modify, distribute, and sell this software commercially. You must keep the license notice and NOTICE file. No warranty provided.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-thing`)
3. Make your changes with tests
4. Run `ruff check . && ruff format . && pytest`
5. Submit a PR

---

## 🙋 Support & Community

- **Issues:** [GitHub Issues](https://github.com/your-org/seo-intelligence-engine/issues)
- **Discussions:** [GitHub Discussions](https://github.com/your-org/seo-intelligence-engine/discussions)
- **Security:** Email security@your-org.com (please don't file public issues for vulnerabilities)

---

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) — Modern, fast web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) — Python SQL toolkit
- [SerpAPI](https://serpapi.com/) — Search API (example provider)
- [WeasyPrint](https://weasyprint.org/) — HTML to PDF
- [Rich](https://rich.readthedocs.io/) — Beautiful terminal output

---

## 📊 Status

| Component | Status |
|-----------|--------|
| Core Intelligence | ✅ Production |
| Web UI | ✅ Production |
| PDF Reports | ✅ Production |
| SerpAPI Provider | ✅ Production |
| Industry Intelligence | ✅ Production |
| AIO/GEO Analysis | ✅ Production |

---

**Made with ❤️ for the SEO community**

*Star this repo if it helps you — it motivates continued development!*