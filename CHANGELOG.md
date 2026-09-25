# Changelog

All notable changes to the SEO Intelligence Engine are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased changes.

## [0.2.0] - 2026-09-26

### Added

- Capability-based search provider registry for separate rankings, AI Overview, and GEO providers.
- AI Overview and GEO observation persistence and historical trend analysis.
- Cross-engine optimization synthesis with deterministic, prioritized recommendations.
- Black-box HTTP acceptance coverage for the site-analysis workflow.
- Production-oriented security controls including SSRF protections, request validation, security headers, API-key authentication, and safe production configuration checks.
- Production Docker and PostgreSQL Compose deployment configuration.
- CodeQL analysis and Dependabot configuration for public-repository maintenance.

### Changed

- Site analysis now supports capability-specific provider routing while retaining backward compatibility with a single provider.
- AI Overview and GEO analysis is explicitly provider-dependent rather than presented as universal coverage.
- Production database migrations are explicit deployment steps rather than automatic startup behavior.
- Production containers run as a non-root user with a single Uvicorn worker because durable jobs currently run inside the application process.
- README, security policy, contribution guidance, and machine-readable project documentation were aligned with the current application contract.
- GitHub Actions dependencies were updated to current supported major versions, including checkout, setup-python, upload-artifact, and CodeQL.
- User-facing product terminology now uses SEO, AEO, and GEO consistently while preserving internal AI Overview implementation identifiers for compatibility.

### Security

- Outbound crawler/search requests validate schemes, private/internal destinations, redirects, response sizes, and localhost policy.
- Production configuration fails fast on unsafe debug, migration, host, and API-authentication settings.
- API keys use constant-time comparison and are not exposed in logs or error messages.
- Request IDs are validated and security response headers are applied by middleware.

### Validation

- Python 3.12 and 3.13 CI coverage remains green.
- Ruff, pytest, dependency auditing, Alembic validation, production Compose validation, and production container builds are part of CI.
- The public-release CodeQL workflow is enabled and passing on main.

## [0.1.0] - 2026-08-25

### Added

- Initial release of SEO Intelligence Engine.
- Deterministic SEO, AI Overview, and GEO intelligence engines.
- Industry-specific intelligence for Casino, Crypto, and Crypto-Casino use cases.
- Evidence/provenance architecture with confidence scoring.
- Server-rendered web UI with dark/light themes.
- PDF reporting through WeasyPrint.
- SQLAlchemy and SQLite persistence with Alembic migrations.
- Search provider abstraction with mock and HTTP providers.
- REST API for search and intelligence workflows.
- Comprehensive automated test coverage.

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for the complete license text.
