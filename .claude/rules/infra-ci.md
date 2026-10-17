---
paths:
  - "infra/**"
  - "justfile"
  - ".githooks/**"
  - "**/Dockerfile*"
  - "**/docker-compose*.yml"
  - "pyproject.toml"
  - "**/pyproject.toml"
  - "pnpm-workspace.yaml"
  - "**/package.json"
  - ".pre-commit-config.yaml"
  - ".importlinter"
---

# Infrastructure, tooling and local quality gate rules

- **Process placement:** TimescaleDB, Redis, MLflow, Django (uvicorn ASGI), the Celery worker and beat, and the management-command consumers all run in **docker compose**. The MT5 gateway runs **natively on Windows**. Never containerise the real gateway, and never run Celery natively on Windows.
- **Networking:** publish Redis and Postgres on `127.0.0.1` only. The native gateway connects to `localhost:6379`, and containers use the service hostnames.
- **Secrets:** compose reads `.env` through `env_file`. Never put values in compose files or Dockerfiles. Commit only `.env.example`, without real values.
- **Pinning:** pin image tags (no `latest`) and Python/Node versions. The `MetaTrader5` pin lives in `apps/gateway/pyproject.toml`.
- **Destructive commands:** `docker compose down -v`, volume pruning and DB drops destroy data. Ask first; the permission rules enforce this too.

## Local quality gate (there is no GitHub CI)

- **No GitHub Actions.** There are no minutes left, so never create `.github/workflows/`. The gate runs on this machine. Design and how to re-enable Actions later: `docs/decisions/0002-branching-and-local-quality-gate.md`.
- **`just check` is the gate:** ruff + pyright + eslint + `tsc`, `tests/structural` (import-linter + invariant tests), Python unit tests, web unit tests, and the contract drift check. Keep it under about 2 minutes, because it runs on every push.
- **Heavier suites run locally on demand** and per the plans: `just test-db` (real Timescale), `just test-integration` (compose offline profile), `just test-leakage`, `just test-e2e`. `/wp-done` runs the ones the WP names.
- **`.githooks/pre-push` runs the gate** and blocks the push if it fails. Enable it with `just hooks` (`git config core.hooksPath .githooks`). Never bypass it with `--no-verify`, and never loosen it to get a push through.
- **The gate must never need an MT5 terminal or Anthropic API tokens.** It uses the fake gateway and fake advisor client. `live_*` tests are excluded.
- **`justfile`** is the command surface CLAUDE.md documents. When you add or rename a target, update CLAUDE.md's Commands table in the same commit.
- **import-linter contracts** in `.importlinter` encode the CLAUDE.md boundaries. Never loosen a contract to make a check pass.

## Dependencies

- Use the uv workspace (one lock, except the gateway's own venv) and the pnpm workspace.
- The P4 `fm_worker` gets its own image and uv project, so torch stays out of the backend image.

See: `docs/plans/F1-backend-platform-django.md` §4.3–4.4, `docs/plans/X2-testing-quality-governance.md` §4.2, §4.5.
