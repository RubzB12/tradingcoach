---
paths:
  - "infra/**"
  - "justfile"
  - ".github/**"
  - "**/Dockerfile*"
  - "**/docker-compose*.yml"
  - "pyproject.toml"
  - "**/pyproject.toml"
  - "pnpm-workspace.yaml"
  - "**/package.json"
  - ".pre-commit-config.yaml"
  - ".importlinter"
---

# Infrastructure, tooling and CI rules

- **Process placement:** TimescaleDB, Redis, MLflow, Django (uvicorn ASGI), the Celery worker and beat, and the management-command consumers all run in **docker compose**. The MT5 gateway runs **natively on Windows**. Never containerise the real gateway, and never run Celery natively on Windows.
- **Networking:** publish Redis and Postgres on `127.0.0.1` only. The native gateway connects to `localhost:6379`, and containers use the service hostnames.
- **Secrets:** compose reads `.env` through `env_file`, and CI uses GitHub secrets. Never put values in compose files, Dockerfiles or workflows. Commit only `.env.example`, without real values.
- **Pinning:** pin image tags (no `latest`) and Python/Node versions. The `MetaTrader5` pin lives in `apps/gateway/pyproject.toml`.
- **Destructive commands:** `docker compose down -v`, volume pruning and DB drops destroy data. Ask first; the permission rules enforce this too.
- **CI must never need an MT5 terminal or Anthropic API tokens.** It uses the fake gateway and fake advisor client. `live_*` tests are excluded.
- **CI jobs:** `lint` (ruff, pyright, eslint, tsc), `structural` (import-linter + `tests/structural`), `py-unit`, `py-db` (Timescale + Redis services), `web-unit`, `contracts` (drift). Integration and leakage run nightly and on PRs to main.
- **`justfile`** is the command surface CLAUDE.md documents. When you add or rename a target, update CLAUDE.md's Commands table in the same commit.
- **Dependency hygiene:** use the uv workspace (one lock, except the gateway's own venv) and the pnpm workspace. The P4 `fm_worker` gets its own image and uv project, so torch stays out of the backend image.
- **import-linter contracts** in `.importlinter` encode the CLAUDE.md boundaries. Never loosen a contract to make a build pass.

See: `docs/plans/F1-backend-platform-django.md` §4.3–4.4, `docs/plans/X2-testing-quality-governance.md` §4.2, §4.5.
