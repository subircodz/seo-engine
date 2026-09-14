# Security Policy

## Supported Versions

Security fixes target the `main` branch. Older commits and unpublished branches are not supported release lines.

## Reporting a Vulnerability

Please do not open a public GitHub issue for a suspected vulnerability.

Use a private GitHub Security Advisory for this repository, or contact the repository owner privately through GitHub if an advisory cannot be created.

Include:

- affected component and endpoint;
- reproduction steps or a minimal proof of concept;
- expected versus observed behavior;
- impact assessment, if known; and
- any suggested mitigation.

Please avoid including real credentials, API keys, customer data, or other secrets in the report.

## Production Security Baseline

Before exposing the service to an untrusted network:

1. Set `SIE_ENVIRONMENT=production`.
2. Use PostgreSQL rather than the development SQLite database.
3. Run Alembic migrations as a deployment step; production configuration automatically disables startup auto-migration.
4. Enable API authentication with long, randomly generated keys.
5. Keep outbound localhost/private-network access disabled.
6. Put the service behind HTTPS and a reverse proxy with appropriate network controls.
7. Keep search/LLM/provider credentials in the deployment secret store, never in Git.
8. Monitor `/health/live` and `/health/ready` separately.
9. Review crawler limits, concurrency, and provider quotas before allowing untrusted users to submit crawl targets.

## Security Scope

The crawler and search integrations treat user-supplied URLs as untrusted input. SSRF protections reject private and metadata-network addresses and validate redirect destinations. Deployments should still use network-level egress controls as defense in depth.
