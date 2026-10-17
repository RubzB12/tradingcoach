# SignalDeck

A personal, educational MT5 signal engine. It reads market data from a MetaTrader 5 **demo** account, produces explainable, calibrated buy/sell/hold signals, paper-tracks them, and offers an on-demand "Ask Claude" second opinion. The stack is Django (Ninja + Channels + Celery) and Next.js 16. **It never places trades.** It is not financial advice.

**Current phase: P0 — Spike: MT5 connectivity.** Status of every work package (WP): `docs/plans/TRACKER.md`.

<!-- Maintainer note: /phase-review updates the "Current phase" line. Keep this file under 150 lines; area detail belongs in .claude/rules/. -->

## Non-negotiable invariants

Hooks (`.claude/hooks/guard_invariants.py`) block violations at edit time, and the structural tests run by `just check` and the pre-push hook (X2-WP02/WP03) block them again. Never work around either. If one gets in the way, stop and ask.

1. **No order code.** Never use `order_send` or `order_check`, in any form. `MetaTrader5` is imported only inside `apps/gateway/`: in production via `sd_gateway/mt5_client.py` (a read-only allowlist), and in the throwaway P0 spike in `apps/gateway/spike/`.
2. **Boundaries.** `apps/gateway` and `packages/sd_*` never import Django or Django apps. `research/` is never imported by app code.
3. **Claude API is deliberate-only.** Only `apps/backend/advisor/{api,views,services}.py` may import `sd_advisor.client`, `sd_advisor.request` or `anthropic`. Never call it from Celery tasks, management commands, schedulers, the gateway, the fm-worker or Prefect flows. Every call starts with a user click and passes the preview/budget gates.
4. **Secrets and identity.** Never read, print or commit `.env`. No secrets in `NEXT_PUBLIC_*`. Never put MT5 login/server/account number/name in packets, logs, fixtures or commits.
5. **Honest validation.** Every feature obeys the `cutoff` contract. Never touch the frozen holdout outside `promote_model`. Results are always reported at 1×/1.5×/2× costs, and never as hit rate alone. Negative results are reported, not tuned away.

## Where things are

The code tree is planned in `docs/plans/F1-backend-platform-django.md` §4.2 and is built from P1 onward.

```
apps/gateway/    sd_gateway — MT5 gateway, native Windows Python 3.12, no Django (F2)
apps/backend/    Django project: config/ + apps core, marketdata, realtime, signals,
                 paper, backtests, mlops, advisor, events, alerts, monitoring (F1)
apps/web/        Next.js 16 dashboard (F3)
apps/fm_worker/  sd_fm — foundation-model Celery worker, own image (P4)
packages/        sd_core, sd_contracts, sd_features, sd_labeling, sd_models,
                 sd_backtest, sd_advisor — framework-free libraries
research/        notebooks only
infra/           docker-compose.yml
docs/plans/      sub-plans (source of truth), README (decision log D1–D14), TRACKER.md
```

Data flow: MT5 terminal → gateway → Redis Streams → ingest (TimescaleDB, Parquet lake) and fan-out (Channels WebSocket) → Next.js. Bar close → dispatcher → Celery inference → signal ledger → paper tracker.

## Environment

- The host is Windows 11. The MT5 terminal and gateway run **natively** (`apps/gateway/.venv`, Python 3.12, `MetaTrader5` version pinned). Everything else runs in **Docker Desktop (WSL2)**. Celery has no native Windows support.
- Shells: Git Bash for POSIX scripts, PowerShell 5.1 for Windows tasks (no `&&`; use `; if ($?) {}`). Always quote paths, because the repo path contains spaces.
- Ports: Next.js 3000 → Django 8000 (`/api`, `/ws` proxied), Postgres/Timescale 5432, Redis 6379 (localhost only), MLflow 5000.

## Commands

The `just` targets exist from F1-WP09 onward. Before that (P0), use `apps/gateway/.venv` directly.

| Task | Command |
|---|---|
| Infra up / down | `just up` / `just down` |
| Backend + workers (dev) | `just dev` |
| Frontend | `just web` (`pnpm --filter web dev`) |
| Gateway (native) | `just gateway` |
| Migrations | `just migrate` |
| **Quality gate** (lint + structural + unit + contract drift, < 2 min) | `just check`. Until X2-WP03 exists: `python -m unittest discover -s tests/structural` |
| Tests / lint / format | `just test` · `just lint` · `just fmt` |
| Heavier suites (run locally) | `just test-db` · `just test-integration` · `just test-leakage` · `just test-e2e` |
| Enable the git pre-push hook | `just hooks` (= `git config core.hooksPath .githooks`; already set in this clone) |
| Regenerate TS contracts | `just contracts` — run after **any** `sd_contracts` or Ninja schema change |
| Install deps | `uv sync` · `pnpm install` |

## How work gets done

- Work is organised as WPs, e.g. `P1-WP02`, defined in `docs/plans/<plan>.md` §5. **A WP's acceptance criteria are its definition of done.**
- Workflow: `/wp-start <WP-ID>` → implement → `/wp-done`. Work on one WP per branch.
- Don't start a WP whose dependencies aren't `done` in the tracker without saying so.
- Stay inside the WP's scope. Note follow-ups in the tracker's Notes column instead of doing them.
- If the design must change, update the plan section **and** the README decision log in the same branch.
- Before closing a WP, run the matching reviewer subagent: `invariants-reviewer` (gateway, advisor, settings, secrets), `leakage-reviewer` (features, labels, models, backtests) or `realtime-perf-reviewer` (charts, stores, WS, fan-out).

## Git

- **`development` is the integration branch; all work lands there.** `main` holds verified, phase-complete states and is updated only at phase boundaries via `/phase-review`.
- **Never commit directly on `development` or `main`** (the guard hook blocks it). Cut a branch from `development`: `wp/<WP-ID>-<short-slug>` (e.g. `wp/P1-WP02-ingest-streams`), or `chore/<slug>` for non-WP work.
- Use small conventional commits that include the WP ID: `feat(P1-WP02): batch COPY upsert in ingest_streams`.
- Landing a branch: after `/wp-done` passes and the user approves, merge into `development` with `git merge --no-ff` (message `merge(<WP-ID>): <summary>`), then push `development` only when asked.
- **Never** push, merge, rebase, reset, force-push or delete branches without asking first. **Never** use `--no-verify`.
- Never commit `.env`, `data/` or recordings outside `tests/fixtures/`.
- **No GitHub Actions** (no minutes left): do not create `.github/workflows`. The quality gate is `just check` plus the `.githooks/pre-push` hook. Rationale and how to re-enable: `docs/decisions/0002-branching-and-local-quality-gate.md`.

## Conventions

- Time: tz-aware **UTC** everywhere, using `sd_core.time`. MT5 broker time is normalised at the gateway.
- Prices: decimals, serialised as strings over the wire and rounded to `symbol.digits`.
- Python: pydantic v2 and Polars in new code (not pandas). ruff + pyright clean. Use structlog, not `print`.
- Generated files (`apps/web/lib/contracts/*`) are never hand-edited.
- Prefer H1/M15 for modelling. M1 is for data and charts.

## Verify before relying

Library and API details change fast: Next.js 16, Lightweight Charts v5, Django Ninja, MetaTrader5, the Claude API. Check the relevant plan's §9 "verify at build time" (or run `/verify-build <plan>`). **Load the claude-api skill before writing any Anthropic SDK code.**
