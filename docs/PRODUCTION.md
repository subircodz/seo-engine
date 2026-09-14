# Production Deployment

This guide runs the SEO Intelligence Engine as a single application container with PostgreSQL. The application intentionally uses one Uvicorn process because durable background jobs run inside the application process; scale job throughput with `SIE_JOBS__CONCURRENCY` first, and design a separate worker service before introducing multiple application processes.

## 1. Prepare the server

Recommended baseline:

- Linux server with Docker Engine and Compose v2
- PostgreSQL storage on a persistent volume
- HTTPS termination at a reverse proxy or managed load balancer
- Firewall exposing only SSH and HTTPS
- At least 2 GB RAM for the base application; PDF/browser features may need more

## 2. Configure secrets

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Set a long random `SIE_API__API_KEYS` value and real provider credentials. Keep `.env.production` outside source control.

Generate an API key with:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

If the PostgreSQL password contains URL-reserved characters, URL-encode it in `SIE_DATABASE_URL`.

## 3. Start PostgreSQL and the application

```bash
docker compose -f docker-compose.production.yml up -d --build
```

The application container waits for PostgreSQL, applies `alembic upgrade head`, and then starts Uvicorn. Automatic migrations are disabled in application configuration; migrations happen explicitly at deployment startup.

## 4. Verify health

Liveness:

```bash
curl -fsS http://127.0.0.1:8000/health/live
```

Readiness:

```bash
curl -fsS http://127.0.0.1:8000/health/ready
```

Expected readiness response:

```json
{"status":"ready","database":"ok"}
```

The health endpoints intentionally do not expose API keys, database URLs, provider URLs, or environment/debug configuration.

## 5. Put HTTPS in front

Do not expose port 8000 directly to the public internet. Put nginx, Caddy, a cloud load balancer, or an equivalent reverse proxy in front of the container and terminate TLS there.

The proxy should:

- redirect HTTP to HTTPS
- forward `X-Request-ID` or allow the application to generate it
- enforce an additional request/body limit appropriate to your deployment
- restrict administrative access if applicable
- preserve Web/API response status codes

## 6. Deployment sequence

For an update:

```bash
git pull --ff-only
docker compose -f docker-compose.production.yml up -d --build
```

Then verify:

```bash
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=100 app
curl -fsS http://127.0.0.1:8000/health/ready
```

If readiness fails, inspect the application logs before routing traffic to the new version.

## 7. Backups

The PostgreSQL volume is persistent, but persistence is not a backup. Configure scheduled PostgreSQL backups before treating the deployment as production data.

At minimum:

- daily full database backup
- retention of multiple backup generations
- off-host backup storage
- periodic restore test

## 8. Important scaling rule

The current architecture starts durable job workers inside the application process. Keep `--workers 1` until job execution is separated from the web process. Running multiple Uvicorn workers would create multiple independent job-worker pools and can increase duplicate work even though the durable queue protects ownership at the database level.

When traffic requires horizontal scaling, the next architecture step is:

```text
                    ┌──────────────┐
Internet ── HTTPS ─▶│ Load Balancer│
                    └──────┬───────┘
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
          API container         API container
                │                     │
                └──────────┬──────────┘
                           ▼
                     PostgreSQL
                           ▲
                           │
                     Job workers
```

Do not implement that split merely to add replicas; make the worker boundary explicit first.
