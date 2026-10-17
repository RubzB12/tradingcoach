---
paths:
  - "**/*.py"
---

# Python rules

These apply to every Python file in the repo.

- **Versions:** Python 3.12 everywhere (the gateway venv is pinned to it). Don't use 3.13-only syntax or APIs.
- **Quality:** code must pass `ruff check`, `ruff format` and `pyright`. Add type hints to every public function and method. `packages/sd_*` run pyright in strict mode.
- **Data models:** use pydantic v2 (`model_validate`, `model_dump`, `ConfigDict`), never v1 APIs. Shared message and wire shapes live in `packages/sd_contracts`.
- **Dataframes:** use Polars in new code. pandas is only allowed where a library demands it (vectorbt, backtesting.py, hmmlearn inputs), and only at that boundary.
- **Time:** always tz-aware UTC via `sd_core.time`. Never use naive `datetime.now()` or `datetime.utcnow()`. Never pass a naive datetime to MT5 or the DB.
- **Money/prices:** use `Decimal` or exact numeric types at storage and wire boundaries. Floats are fine inside numeric/ML code.
- **Logging:** use `structlog`, never `print`. `print` is only allowed in `apps/gateway/spike/`, `scripts/` and `research/`. Never log secrets, MT5 credentials or account identifiers.
- **Errors:** catch specific exceptions. Never write bare `except:` or swallow exceptions silently in long-running loops; log, count and continue, or re-raise.
- **Imports:** respect the boundaries in CLAUDE.md. `packages/sd_*` never import Django. Never import `research/`. Don't use dynamic imports (`importlib`, `__import__`) to get around those rules.
- **Dependencies:** add them with `uv add` to the right workspace member, and never hand-edit lockfiles. Hook scripts in `.claude/hooks/` are stdlib-only.
- **Tests** sit next to the package (`packages/<pkg>/tests`, `apps/<app>/tests`). See `.claude/rules/testing.md`.

See: `docs/plans/F1-backend-platform-django.md` §4.3.
