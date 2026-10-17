# F1 — Backend Platform (Django)

> **Type:** Foundation · **Scheduled in:** Phase 1 (WP01–WP09), Phase 2 (WP10)
> **Master plan refs:** §2 Architecture, "Backend choices and rationale", Monorepo, Dev setup
> **Index:** [README](README.md)

## 1. Goal and context

This plan sets up the server-side platform that every later phase builds on: the monorepo, the Django project, ASGI serving, REST (Django Ninja), WebSocket (Django Channels), background jobs (Celery + beat), Redis, TimescaleDB, MLflow, and the typed contract pipeline to Next.js.

The master plan was written for FastAPI. This plan replaces it with Django and keeps the architecture's intent the same:

- FastAPI never calls MT5. Django never calls MT5 either. Only the gateway ([F2](F2-mt5-gateway.md)) does.
- The API is async throughout. Blocking work (DuckDB, model inference) runs in `asyncio.to_thread`/`sync_to_async` or Celery.
- Redis Streams is the bus, and Redis keys hold live state.
- TimescaleDB stores bars, ticks and ledgers. A Parquet + DuckDB lake holds research data.

## 2. Scope

**In:** repo bootstrap, Python and JS toolchains, docker-compose infrastructure, Django skeleton and settings, ASGI + Channels, Ninja API root, Celery, TimescaleDB helpers, the contract pipeline, the justfile/runbook, and structured logging.

**Out:**
- MT5 access ([F2](F2-mt5-gateway.md))
- Frontend ([F3](F3-frontend-platform-nextjs.md))
- Domain models for bars/signals/etc. (in the phase plans)
- CI workflow and test harness ([X2](X2-testing-quality-governance.md))
- Prefect (moved to [P4](P4-deep-learning-foundation-models.md))

## 3. Dependencies

- [P0](P0-spike-mt5-connectivity.md) must be finished, so the MT5 host decision is settled.
- Docker Desktop with the WSL2 backend must be installed on the Windows host.

## 4. Design

### 4.1 Django adaptation decisions

| Master plan (FastAPI stack) | SignalDeck (Django stack) | Notes |
|---|---|---|
| FastAPI + uvicorn | **Django 5.2 LTS** (or current 6.x — verify at build) on **uvicorn** via `config/asgi.py` | Run with `uvicorn config.asgi:application --reload` in dev |
| pydantic v2 routers | **Django Ninja** routers, `ninja.Schema` (pydantic v2) | OpenAPI served at `/api/v1/openapi.json` |
| FastAPI WebSocket `/ws` | **Django Channels** `AsyncJsonWebsocketConsumer` + `channels-redis` | One socket per tab at `/ws/`, multiplexed envelope |
| `sse-starlette` | Async view returning `StreamingHttpResponse(async_gen, content_type="text/event-stream")` | Used for Ask Claude and LLM explanation streaming |
| APScheduler / arq / Dramatiq | **Celery 5 + beat**, Redis broker | Runs in Docker (Linux), because Celery has no native Windows support |
| Long-running workers | **Django management commands** (`ingest_streams`, `stream_fanout`, `bar_close_dispatcher`, `paper_tracker`) | Each runs as its own compose service |
| SQLAlchemy / asyncpg | Django ORM (async methods where useful); **psycopg 3 `COPY`** for bulk bar/tick inserts | Hypertables are created via migrations |
| (none) | **Django admin** | Covers symbols, settings, ledgers, budget caps |
| Auth | Single-user session auth; Next.js rewrites make `/api` and `/ws` same-origin | Channels `AuthMiddlewareStack` |

### 4.2 Repository layout

```
signaldeck/  (= this project folder)
├─ apps/
│  ├─ web/                    # Next.js 16 (F3)
│  ├─ backend/                # Django project
│  │  ├─ manage.py
│  │  ├─ config/              # settings/{base,dev,test,prod}.py, asgi.py, urls.py, celery.py, routing.py
│  │  ├─ core/                # UserSettings singleton, health, shared utils, admin bootstrap
│  │  ├─ marketdata/          # Symbol, Bar, Tick, ingest/backfill commands         (P1)
│  │  ├─ realtime/            # Channels consumer, envelope, stream_fanout command    (P1)
│  │  ├─ signals/             # Signal ledger, explanations, inference tasks         (P2/P3)
│  │  ├─ paper/               # paper tracker, outcome stats                         (P2)
│  │  ├─ backtests/           # BacktestRun, tasks, reports                          (P2)
│  │  ├─ mlops/               # model registry mirror, promotion                     (P3)
│  │  ├─ advisor/             # Ask Claude API + SSE (only importer of sd_advisor)   (X1)
│  │  ├─ events/              # economic calendar + news                             (P5)
│  │  ├─ alerts/              # alert rules engine                                   (P5)
│  │  └─ monitoring/          # drift reports                                        (P5)
│  └─ gateway/                # sd_gateway — MT5 gateway, no Django (F2)
├─ packages/                  # framework-agnostic Python libs (no Django imports)
│  ├─ sd_core/                # domain types, settings base, time utils (UTC/broker), symbols, timeframes
│  ├─ sd_contracts/           # pydantic models for stream messages + WS envelope → JSON Schema
│  ├─ sd_features/            # indicator + feature pipelines (Polars/TA-Lib)        (P2/P3)
│  ├─ sd_labeling/            # triple-barrier, meta-labels, weights                 (P3)
│  ├─ sd_models/              # model plug-in interface + implementations            (P2–P4)
│  ├─ sd_backtest/            # cost model, simulators, metrics, adapters            (P2–P4)
│  └─ sd_advisor/             # Ask Claude packet/prompt/schema/client/budget        (X1)
├─ research/                  # marimo/Jupyter notebooks — never imported by apps
├─ infra/docker-compose.yml   # timescaledb, redis, mlflow, backend, workers, (P4) prefect, fm-worker
├─ data/                      # git-ignored: lake/, recordings/, mlflow-artifacts/
├─ docs/                      # plans/, runbook.md, reports/, decisions/
├─ tests/                     # cross-package + integration tests (X2)
├─ .github/workflows/
├─ pyproject.toml             # uv workspace root
├─ pnpm-workspace.yaml
└─ justfile
```

Python packages use the `sd_` prefix so they have distinct top-level import names, which import-linter needs. Django apps keep short names inside `apps/backend`.

### 4.3 Python toolchain

- **uv workspace** with members `apps/backend`, `apps/gateway` and `packages/*`. Use one lockfile, except the gateway, which has its own pinned Windows venv (see F2).
- **Python 3.12** is the default everywhere, for the widest ML wheel support. The gateway pins Python 3.12 and `MetaTrader5==<pinned>`.
- **ruff** handles lint and format. Enable `flake8-tidy-imports` `banned-api`: `MetaTrader5.order_send` and `MetaTrader5.order_check` are banned, and `anthropic` is banned outside `sd_advisor`.
- **pyright** runs in basic mode, strict for `packages/*`.
- **pre-commit** runs ruff, pyright (fast subset), the pnpm lint and the `order_send` grep.

### 4.4 Infrastructure (docker-compose)

| Service | Image / command | Port | Notes |
|---|---|---|---|
| `db` | `timescale/timescaledb-ha:pg17` (verify tag) | 5432 | Databases: `signaldeck`, `mlflow`, `optuna` (init script) |
| `redis` | `redis:7-alpine` with AOF | 6379 | Streams, Channels layer, Celery broker, cache |
| `mlflow` | `ghcr.io/mlflow/mlflow` | 5000 | Backend store `postgresql://…/mlflow`, artifacts in `./data/mlflow-artifacts` |
| `backend` | `uvicorn config.asgi:application` | 8000 | Django ASGI (HTTP + WS) |
| `worker` | `celery -A config worker -Q default,backtest,ml` | — | |
| `beat` | `celery -A config beat` | — | Schedule lives in code (`config/celery.py`) |
| `ingestor` | `python manage.py ingest_streams` | — | P1 |
| `fanout` | `python manage.py stream_fanout` | — | P1 |
| `dispatcher` | `python manage.py bar_close_dispatcher` | — | P2 |
| `paper` | `python manage.py paper_tracker` | — | P2 |
| `fake-gateway` | `python -m sd_gateway --impl fake` | — | Profile `ci`/`offline` (F2-WP06) |

On Windows, the real gateway runs **natively** and connects to `localhost:6379` (the published Redis port). The browser reaches Next.js on `:3000`, which proxies to `:8000`.

### 4.5 Settings and secrets

- `config/settings/base.py` reads env via `django-environ`. Keep one `.env` at the repo root. Commit `.env.example`, and never commit `.env`.
- Keys: `DATABASE_URL`, `REDIS_URL`, `MLFLOW_TRACKING_URI`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS=http://localhost:3000`, `ANTHROPIC_API_KEY` (read only by `sd_advisor` via the advisor app), `ADVISOR_MODEL_ID=claude-opus-5-5`, `MT5_LOGIN/MT5_PASSWORD/MT5_SERVER` (gateway only).
- The `core.UserSettings` singleton model stores user-tunable values: risk-per-trade %, advisor daily/monthly caps, skip-preview flag, notification prefs and watchlist defaults. You edit them in admin and through `GET/PUT /api/v1/settings`.

### 4.6 API conventions (Django Ninja)

- The root is `NinjaAPI(urls_namespace="api", version="1")`, mounted at `/api/v1/`. Each app has one `Router`.
- Errors use the envelope `{"error": {"code": str, "message": str, "details": {}}}`, which an exception handler produces.
- Auth: `django_auth` (session) plus CSRF on unsafe methods. Requests from the browser always arrive via the Next.js proxy, so they are same-origin.
- Pagination: cursor-based for time series (`?before=<ts>&limit=`) and Ninja `PageNumberPagination` for ledgers.
- Time is always ISO-8601 UTC with `Z`. Prices are decimals serialized as strings, rounded to `symbol.digits`.
- `GET /api/v1/health` returns DB ok, Redis ok, gateway heartbeat age (s), Celery ping, and versions.

### 4.7 Realtime conventions (Channels)

- Route `ws/` → `realtime.consumers.DashboardConsumer`.
- **Server→client envelope:** `{"channel": "tick|bar|signal|explain|forecast|pipeline|health|alert", "symbol": str|null, "tf": str|null, "seq": int, "ts": iso, "payload": {...}}`
- **Client→server ops:** `{"op": "subscribe|unsubscribe|ping", "channel": str, "symbol": str|null, "tf": str|null}`
- Channel-layer groups: `sym.<SYMBOL>.tick`, `sym.<SYMBOL>.bar.<TF>`, `signals`, `health`, `alerts`. Symbols are sanitized to `[A-Za-z0-9._-]`.
- `seq` is assigned per (channel, symbol, tf) by `stream_fanout`. The client uses gaps to trigger a REST resync.
- msgpack framing is optional, behind `?format=msgpack` (binary frames via `msgpackr` on the client).

### 4.8 Celery conventions

- Queues: `default` (housekeeping, lake export), `backtest` (UI-launched runs), `ml` (training, inference fallbacks). P4 adds `fm`.
- Tasks are idempotent and keyed by natural IDs (e.g. `run_backtest(run_id)`). Results go to Postgres, not the Celery result backend.
- **Rule:** no Celery task module may import `sd_advisor` (deliberate-only; enforced by [X2-WP02](X2-testing-quality-governance.md#5-work-packages)).

### 4.9 TimescaleDB patterns

- Hypertables are created in migrations with a custom operation `core.migrations_ops.CreateHypertable(table, time_column, chunk_interval)`. It wraps `RunSQL` and has a reverse.
- Composite primary keys use Django 5.2's `models.CompositePrimaryKey("symbol", "tf", "time")`, so the ORM can read hypertables. Writes from ingest go through `core.db.copy_rows(table, columns, rows)` (psycopg 3 `cursor.copy`) with `ON CONFLICT`-style dedupe via a staging temp table + `INSERT … ON CONFLICT DO UPDATE`.
- Helper operations cover the compression policy, retention policy and continuous aggregates (`CreateContinuousAggregate`).

### 4.10 Typed contracts

- `sd_contracts` holds the pydantic models for: the stream messages (`TickMsg`, `BarMsg`, `HealthMsg`, `HistoryRequest`/`HistoryResponse`), the WS envelope and every channel payload, and later `SignalMsg`, `ExplainMsg`, `ForecastMsg` and `AdvisorAnswer`.
- `just contracts` does three things:
  1. Exports the JSON Schema from `sd_contracts`. It runs `json-schema-to-typescript` to produce `apps/web/lib/contracts/ws.ts`.
  2. Dumps the Ninja OpenAPI. It runs `openapi-typescript` to produce `apps/web/lib/contracts/api.ts`.
  3. Fails if the git diff is non-empty in CI (drift check, [X2-WP04](X2-testing-quality-governance.md#5-work-packages)).
- Ninja schemas reuse `sd_contracts` models wherever the shape is shared, so there is one source of truth.

## 5. Work packages

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| F1-WP01 | **Repo + toolchain bootstrap:** git init, `.gitignore` (both already done with the Claude setup in `chore/claude-setup`; extend as needed), uv workspace root, pnpm workspace, ruff/pyright config incl. banned-api, pre-commit, `.env.example`, `.editorconfig` | 3 | M | P0 done | `uv sync` and `pnpm i` succeed on a clean clone, and `pre-commit run -a` passes |
| F1-WP02 | **docker-compose infrastructure:** `db` (Timescale, init script creating 3 DBs + extension), `redis` (AOF), `mlflow`, named volumes, healthchecks | 3 | M | WP01 | `just up` brings all three services to healthy, and the MLflow UI loads at :5000 |
| F1-WP03 | **Django skeleton:** `apps/backend`, split settings, `core` app, `UserSettings` singleton + admin, superuser bootstrap command `ensure_admin` | 3 | M | WP02 | `manage.py check --deploy` (dev-relaxed) passes and admin shows `UserSettings` |
| F1-WP04 | **ASGI + Channels:** `config/asgi.py` ProtocolTypeRouter, `channels-redis` layer, `realtime` app, `DashboardConsumer` with subscribe/unsubscribe/ping and envelope validation via `sd_contracts` | 3 | M | WP03 | A WS client can connect, subscribe and receive a test `group_send`, and an invalid op gets an error frame |
| F1-WP05 | **Ninja API root:** versioned API, session auth + CSRF, error envelope handler, `GET /health` (db, redis, gateway heartbeat age, celery ping) | 2.5 | M | WP03 | `/api/v1/docs` renders, `/health` returns all checks, and unauthenticated unsafe calls are rejected |
| F1-WP06 | **Celery:** `config/celery.py`, queues, beat schedule in code, compose `worker` + `beat` services, `core.tasks.ping` | 2.5 | M | WP02, WP03 | `ping.delay()` round-trips, and beat logs the scheduled heartbeat task |
| F1-WP07 | **Timescale helpers:** `CreateHypertable`, `AddCompressionPolicy`, `AddRetentionPolicy`, `CreateContinuousAggregate` migration ops, `core.db.copy_rows` with staging upsert | 3 | M | WP03 | A test migration creates a hypertable, and 100k rows insert via `copy_rows` in < 2 s locally with duplicates upserted |
| F1-WP08 | **Contract pipeline:** `sd_contracts` package with envelope + stream message models, JSON Schema export, `openapi-typescript` + `json-schema-to-typescript`, `just contracts` | 3 | M | WP04, WP05 | The generated TS types compile in `apps/web`, and changing a pydantic field changes the TS output |
| F1-WP09 | **justfile + runbook:** `up/down/dev/web/gateway/migrate/test/contracts/lint/fmt/shell`, plus `docs/runbook.md` (first-time setup on Windows, ports, troubleshooting) | 1 | M | WP01–WP08 | A fresh setup can be done following only the runbook |
| F1-WP10 | **Structured logging:** `structlog` JSON logs, request-ID middleware, log correlation for WS and Celery, rotating files in `data/logs` | 1.5 | S | WP03 | One request ID can be traced from an HTTP log to the Celery task logs |

**Totals:** Phase 1 = 24 h · Phase 2 = 1.5 h

## 6. Testing (see [X2](X2-testing-quality-governance.md))

- `pytest-django` smoke tests: settings load, `/health` responds, and admin login works.
- A Channels `WebsocketCommunicator` test for the subscribe/unsubscribe/ping flow and envelope validation.
- Migration-op tests run against a real Timescale service container (CI).
- Contract drift check in CI ([X2-WP04](X2-testing-quality-governance.md#5-work-packages)).

## 7. Exit criteria

F1 has no exit criterion of its own in the master roadmap. It supports Phase 1's *"Monorepo, compose, typed WS contract"* deliverables. Measurable checks:

- [ ] On a clean clone, `just up && just migrate && just dev` gives a working admin, API docs and WS echo in ≤ 15 min following the runbook.
- [ ] `just contracts` is deterministic: running it twice produces no diff.
- [ ] No Django import exists anywhere under `packages/` or `apps/gateway` (import-linter green).

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Celery can't run on native Windows | Run all workers in Docker. Only the MT5 gateway is native |
| Async/sync mixing in Django (ORM in async consumers) | Use the async ORM API (`aget`, `acreate`, `async for`) in consumers and SSE views. Wrap anything else with `sync_to_async(thread_sensitive=False)` |
| Hypertable + Django ORM friction (PK, migrations) | Use composite PKs, raw-SQL migration ops and COPY for writes. The ORM is for reads and admin only |
| Docker Desktop networking to the native gateway | Publish Redis on `127.0.0.1:6379`. The gateway connects to localhost, and containers use the `redis` hostname |
| OneDrive syncing `node_modules`/`.venv`/`data` | **Move the repo out of OneDrive** (e.g. `C:\dev\signaldeck`), or exclude those folders. OneDrive locks files and slows installs. Decide this before F1-WP01 |

## 9. Open questions / verify at build time

- Django 5.2 LTS vs the latest 6.x: confirm `CompositePrimaryKey` behaviour with admin and Ninja, and Channels compatibility.
- The exact TimescaleDB image tag and Postgres major version.
- Django Ninja's current major version and its pydantic v2 support (should be fine; verify).
- Whether to use `django-celery-beat` (DB-editable schedules) or the code schedule. Default: code; revisit in P5 for alert schedules.
