# SEO Intelligence Engine — Roadmap

> **ROADMAP.md is the strategic engineering source of truth.**
> README.md explains the current product and how to run it.
> This document records the verified current state and the next engineering priorities.

## 1. Product Direction

SEO Intelligence Engine (SIE) is a self-hosted **SEO + AEO + GEO intelligence platform**.

The long-term direction is to make search-visibility analysis more evidence-backed, composable, historical, and actionable across traditional search and AI-search surfaces.

The project deliberately avoids claiming universal coverage of search engines, AI answer engines, or external data providers.

## 2. Verified Current State

The following capabilities are implemented in the current `main` branch:

### Website and SEO intelligence

- Website crawling with robots, redirect, response-size, concurrency, and SSRF controls.
- Technical SEO auditing with deterministic rules.
- Content-quality and page-level analysis.
- Internal-link and site-architecture analysis.
- Keyword extraction from crawled content.
- Page-performance signals based on collected HTML/resource information.
- CrUX integration for real-user Core Web Vitals when configured.
- Entity extraction and entity-related analysis.

### Search intelligence

- Search-provider abstraction.
- Capability-based provider registry for rankings, AEO, and GEO.
- Search-ranking collection and persistence.
- SERP feature analysis.
- Ranking volatility analysis.
- Keyword cannibalization analysis.
- Search-opportunity analysis.
- Country-wise ranking analysis.
- Competitor ranking comparison.

### AEO and GEO

- AEO models and deterministic analytics.
- SerpAPI-backed AEO extraction when configured.
- GEO models and deterministic analytics.
- OpenAI-compatible LLM-backed GEO provider.
- AEO/GEO observation persistence.
- Historical AEO/GEO trend calculations.
- AEO/GEO inputs available to search-intelligence and optimization workflows.

### Cross-engine recommendations

- Deterministic cross-engine optimization synthesis.
- Recommendations covering ranking, cannibalization, volatility, SERP features, opportunities, AEO, GEO, performance, and entities.
- Priority scoring and recommendation summaries.
- Site Analysis integrates the optimization synthesis into the analysis result.

### Application and reporting

- FastAPI web application and HTTP API.
- Server-rendered web UI.
- PDF report generation through WeasyPrint.
- PostgreSQL and SQLite support with Alembic migrations.
- Durable background jobs with explicit at-least-once execution semantics.
- Production Docker image and PostgreSQL Compose deployment.

### Engineering and release quality

- Unit and integration test coverage.
- Black-box HTTP acceptance coverage for the site-analysis workflow.
- Ruff linting and formatting checks.
- Dependency auditing with `pip-audit`.
- Alembic migration validation.
- Production Compose validation and container build validation.
- CodeQL analysis.
- Dependabot for dependency and GitHub Actions updates.
- Apache License 2.0.

## 3. Explicit Limitations

These are intentionally **not** presented as completed capabilities:

- Universal coverage of every search engine or AI answer surface.
- Guaranteed Google AI Overview coverage for every query or geography.
- Universal GEO coverage across every generative engine.
- A complete backlink intelligence provider integration.
- JavaScript rendering as a general crawler capability.
- Full DNS-rebinding/TOCTOU protection for every possible network race.
- Exactly-once background-job execution.
- Historical comparison and forecasting across every analysis dimension.
- Advanced NER/embedding-based semantic understanding.

## 4. Next Priorities

### Priority 1 — Provider and capability maturity

- Add additional search/AEO/GEO providers behind the existing provider abstraction.
- Improve capability discovery and provider-health reporting.
- Make provider limitations visible in analysis results instead of silently degrading.

### Priority 2 — Historical search intelligence

- Extend historical storage and comparison beyond AEO/GEO observations.
- Add time-series views for rankings, visibility, opportunities, and competitor movement.
- Add trend and change detection to reports.

### Priority 3 — Evidence and diagnosis depth

- Expand evidence provenance so recommendations can consistently point back to their source signals.
- Integrate diagnosis and evidence-building components more deeply into Site Analysis.
- Improve recommendation explanations without requiring an LLM for core SEO decisions.

### Priority 4 — Crawler and semantic depth

- Add optional JavaScript rendering where justified.
- Improve structured-data validation and enrichment.
- Replace or complement regex entity extraction with pluggable NER/semantic providers.
- Improve topical and semantic coverage analysis.

### Priority 5 — Authority and competitive intelligence

- Introduce a provider abstraction for backlink/authority data.
- Add stronger competitor gap analysis when reliable external data is available.

### Priority 6 — Production operations

- Improve observability and provider-level diagnostics.
- Separate durable job workers from the web process before introducing multiple application workers.
- Add stronger operational guidance for backups, upgrades, and failure recovery.

## 5. Engineering Rules

Every future change should follow these rules:

1. Verify the existing implementation before changing documentation or claiming a capability.
2. Keep README claims aligned with the actual application contract.
3. Keep provider-dependent capabilities explicitly provider-dependent.
4. Prefer deterministic analysis for core SEO behavior.
5. Preserve evidence and provenance wherever practical.
6. Treat security, tests, migrations, CI, and documentation as part of the feature.
7. Do not mark a roadmap item complete until the implementation and tests support the claim.
8. Do not use roadmap status as a substitute for code verification.

## 6. Release Gate

A capability should be considered production-ready only when it has:

- a real implementation,
- integration with the relevant application workflow,
- automated tests,
- documented limitations,
- safe configuration behavior,
- and a reproducible validation path.

The public repository should describe what the current code can actually do—not what the project may eventually become.
