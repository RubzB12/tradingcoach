---
paths:
  - "apps/backend/**"
---

# Django backend rules

These apply to the Django project, its apps, the Celery workers and the management commands.

## Structure

- Each app has `models.py`, `api.py` (one Ninja `Router`), `schemas.py`, `admin.py`, `tasks.py` (Celery), `services.py` (business logic) and `management/commands/` (long-running consumers).
- Business logic lives in `services.py` or in `packages/sd_*`, never in views or tasks. Views and tasks stay thin.
- Mount routers on the single `NinjaAPI` at `/api/v1/`. Use the error envelope `{"error": {"code", "message", "details"}}` through the shared handler.
- If a schema matches a stream/WS message, reuse the `sd_contracts` model rather than redefining it. After any schema change, run `just contracts`.
- Register every model in `admin.py`. The admin is the operator UI for symbols, settings and ledgers.

## Async and realtime

- Channels consumers and SSE views are async. Use the async ORM API (`aget`, `acreate`, `afilter`, `async for`), never sync ORM calls inside async code. Wrap unavoidable sync code with `sync_to_async`.
- Never call blocking I/O (DuckDB, model inference, heavy Polars) in the ASGI event loop. Use `asyncio.to_thread` or hand it to a Celery task.

## Celery and consumers

- Tasks are **idempotent**, keyed by natural IDs (`run_backtest(run_id)`), and write results to Postgres rather than the result backend. Each one is routed to a queue: `default`, `backtest`, `ml` or `fm`.
- **No Celery task, beat schedule or management command may import `sd_advisor` or `anthropic`.** The Claude API is deliberate-only (CLAUDE.md invariant 3).
- Long-running Redis-Streams consumers (`ingest_streams`, `stream_fanout`, `bar_close_dispatcher`, `paper_tracker`, `alerts_engine`) are management commands. They use consumer groups, `XACK` only after the DB commit, and shut down gracefully on SIGTERM.
- Inference triggers off `bars.persisted` (emitted after commit), never the raw `bars:*` stream.

## Settings and data

- Settings come only from env via `django-environ` in `config/settings/`. Never hard-code hosts, keys or credentials.
- Never edit a migration that has already been applied. Add a new one instead. Hypertable rules are in `.claude/rules/timescale-data.md`.
- Auth is single-user Django session + CSRF. Never add `csrf_exempt` to unsafe endpoints.

See: `docs/plans/F1-backend-platform-django.md` §4.1, §4.6–4.8.
