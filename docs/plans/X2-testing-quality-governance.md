# X2 — Testing, Quality and Model Governance

> **Type:** Cross-cutting · **Scheduled in:** Phase 1 (WP01–WP05, 11 h), Phase 2 (WP06–WP07, 7 h), Phase 3 (WP08–WP09, 7 h)
> **Master plan refs:** Testing strategy (unit, leakage, contract, gateway, integration, frontend, advisor, model governance); Recommendation 2 ("Make 'no execution' structural"); §4 validation protocol; §7.1 deliberate-only
> **Index:** [README](README.md)

## 1. Goal and context

The two most important properties of SignalDeck are **structural**:

- it can never place orders
- it can never call Claude on its own

Its value also depends on **honest validation**: no leakage, and no overfitting dressed up as edge. This plan makes those properties testable and enforced in CI. It also defines the test harness (fake MT5, fake Anthropic, recorded data) so the whole stack runs on CI and on a machine without an MT5 terminal.

## 2. Scope

**In:** test layout and tooling, structural contracts (import-linter + AST/grep tests), CI workflows, contract/WS tests, recorded fixtures, the integration job, Playwright + visual regression, the leakage suite, and the model promotion gate.

**Out:** feature-specific unit tests, which live with each WP. The advisor test cases are listed here but built in [X1-WP07/WP19](X1-ask-claude-advisor.md#5-work-packages).

## 3. Dependencies

- [F1](F1-backend-platform-django.md) skeleton
- [F2-WP06](F2-mt5-gateway.md#5-work-packages) fake MT5
- [P0-WP07](P0-spike-mt5-connectivity.md#5-work-packages) recordings

## 4. Design

### 4.1 Test layout and tools

| Area | Tooling | Location |
|---|---|---|
| Python unit | pytest, hypothesis, pytest-django, factory-boy, freezegun/time-machine | `packages/*/tests`, `apps/*/tests` |
| Async/Channels | pytest-asyncio, `channels.testing.WebsocketCommunicator` | `apps/backend/realtime/tests` |
| DB | Real TimescaleDB service container (no SQLite: hypertables + continuous aggregates) | CI service `db` |
| Cross-cutting | Structural tests, integration | `tests/` |
| Frontend unit | Vitest + Testing Library + MSW | `apps/web/**/*.test.ts(x)` |
| E2E | Playwright against compose profile `offline` (fake gateway) | `apps/web/e2e` |
| Visual regression | Playwright screenshots on fixed fixtures | `apps/web/e2e/visual` |
| Lint/types | ruff, pyright, eslint, `tsc --noEmit` | CI |

**Markers:**
- `unit` (default)
- `db`
- `integration` (compose)
- `live_mt5` (manual, never in CI)
- `live_claude` (manual, spends money, never in CI)

### 4.2 Structural contracts

**import-linter** (`.importlinter` at the repo root):

```ini
[importlinter]
root_packages = sd_core sd_contracts sd_features sd_labeling sd_models sd_backtest sd_advisor sd_gateway sd_fm config core marketdata realtime signals paper backtests mlops advisor events alerts monitoring
include_external_packages = True

[importlinter:contract:packages-are-framework-free]
name = Shared packages never import Django or Django apps
type = forbidden
source_modules = sd_core sd_contracts sd_features sd_labeling sd_models sd_backtest sd_advisor sd_gateway sd_fm
forbidden_modules = django channels ninja celery config core marketdata realtime signals paper backtests mlops advisor events alerts monitoring

[importlinter:contract:mt5-only-in-gateway]
name = MetaTrader5 is imported only by the gateway
type = forbidden
source_modules = sd_core sd_contracts sd_features sd_labeling sd_models sd_backtest sd_advisor sd_fm config core marketdata realtime signals paper backtests mlops advisor events alerts monitoring
forbidden_modules = MetaTrader5

[importlinter:contract:no-live-trading-adapters]
name = NautilusTrader live adapters are never imported
type = forbidden
source_modules = sd_backtest
forbidden_modules = nautilus_trader.adapters nautilus_trader.live

[importlinter:contract:core-is-lowest]
name = sd_core depends on nothing internal
type = forbidden
source_modules = sd_core
forbidden_modules = sd_contracts sd_features sd_labeling sd_models sd_backtest sd_advisor sd_gateway sd_fm
```

**AST/grep tests** (`tests/structural/`). These are more precise than import-linter for allowlists:

| Test | Rule |
|---|---|
| `test_no_order_code` | Repo-wide grep (excluding `docs/`, `CLAUDE.md`, `.claude/` and `tests/structural/`, which describe the ban) for `order_send\|order_check` → must be empty. Also asserts the `sd_gateway.mt5_client` allowlist contains only read-only functions |
| `test_advisor_deliberate_only` | AST-scan every `.py`. Only `apps/backend/advisor/{api,views,services}.py` may import `sd_advisor.client`, `sd_advisor.request` or `anthropic`. **Explicitly fails** for any `*/tasks.py`, `*/management/commands/*`, `config/celery.py`, `sd_gateway/*`, `sd_fm/*`, Prefect flows |
| `test_no_secrets_to_browser` | `apps/web` contains no `NEXT_PUBLIC_*KEY*`/`*SECRET*`/`ANTHROPIC*` references. `.env.example` has no real values |
| `test_packet_has_no_account_identifiers` | Packet built from fixtures where account_info includes login/server/name contains none of them (also X1-WP07) |
| `test_gateway_no_django` | Covered by import-linter, plus a grep for `django` in `apps/gateway` |

**Edit-time mirror:** `.claude/hooks/guard_invariants.py` (a Claude Code PreToolUse hook, tested by `tests/structural/test_claude_hooks.py`) blocks the same violations while Claude edits files. It is a fast first layer only. These CI tests remain authoritative, and the two must be kept in sync when a rule changes.

### 4.3 Leakage suite (P3, master "Leakage tests")

| Test | Implementation |
|---|---|
| **Cutoff compliance** | For every function in the `FEATURES` registry: compute on data up to t, then on data up to t+k. Values at all times ≤ t must be identical. Parametrized over the registry, so new features are covered automatically |
| **Shifted-future canary** | Master wording: *"a shifted-future canary feature must produce worse-than-random OOS results if leakage handling works."* Implementation: (a) a canary feature built from future returns must be **rejected** by the cutoff guard at build time; (b) with the guard bypassed (test-only flag), the harness must show a large OOS skill jump. This proves the detector actually catches leaks. (c) A canary built from future data *beyond the label horizon* that slips through purging must not improve purged-CV OOS results |
| **Label permutation** | Shuffle labels within the training set → OOS AUC ≈ 0.5 ± 0.03 and expectancy ≈ −costs. A real edge here means leakage |
| **Purge/embargo correctness** | No training event's `[t0, t1]` overlaps any test window. The embargo gap is ≥ the configured %. Property-based test with hypothesis |
| **HMM future-invariance** | Filtered regime probabilities for times ≤ t don't change when rows after t are appended |
| **As-of join** | HTF features at a decision bar only use HTF bars **closed** at or before that bar's close |
| **Holdout guard** | `load_dataset()` raises when asked for rows ≥ `holdout_start` without `final_eval=True` |

### 4.4 Contract and WS tests

- **Snapshot tests:** the generated `api.ts`/`ws.ts` must match the committed versions (drift check runs `just contracts` and then `git diff --exit-code`).
- **pydantic ↔ TS:** a round-trip fixture per channel payload is validated in Python and type-checked in TS (`tsc` on a fixture file).
- **WS envelope fuzzing:** hypothesis generates malformed client ops. The consumer must answer with error frames and never crash or join an unintended group.

### 4.5 CI workflows (`.github/workflows/`)

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | push / PR | `lint` (ruff, pyright, eslint, tsc), `structural` (import-linter + `tests/structural`), `py-unit`, `py-db` (Timescale + Redis services), `web-unit` (vitest), `contracts` (drift) |
| `integration.yml` | PR to main, nightly | Compose `offline` profile: fake gateway (1 recorded trading day at 60×) → ingest → dispatcher → inference → WS assertions, plus Playwright E2E and visual regression |
| `leakage.yml` | Nightly + PRs touching `sd_features`/`sd_labeling`/`sd_backtest` | Leakage suite on a fixture dataset |

The gateway runs on Windows only in production, but in CI its unit tests run on Linux using fake MT5. An optional `windows-latest` job checks that `sd_gateway` imports and that its tests pass with the real package installed (but no terminal).

### 4.6 Model governance (master "Model governance")

Promotion happens only through `python manage.py promote_model --name signaldeck-{group}-{tf} --version N`. It refuses unless:

1. The MLflow run has the required artifacts: WF report, reliability plot, cost sensitivity (1/1.5/2×), feature list + hash, data snapshot ID, trial count.
2. A **frozen-holdout evaluation** was run for both the candidate and the current champion, using the same data and cost model.
3. The candidate beats the champion on the configured criteria. The default is **DSR higher and Brier ≤ champion's**, and **expectancy at 1.5× costs > 0**.
4. The leakage suite passed on the commit that trained the model (recorded in the run tags).

On success, it moves the `champion` alias, writes a `PromotionRecord`, and publishes `mlops.reload`. On failure, it writes a record with the reasons. Drift-triggered retrains (P5) only produce **challengers**, and promotion stays manual through this gate.

## 5. Work packages

| ID | Task | Est. h | Pri | Phase | Depends on | Acceptance criteria |
|---|---|---|---|---|---|---|
| X2-WP01 | **Test harness:** pytest config + markers, pytest-django test settings, factories, Timescale/Redis fixtures, Vitest/MSW base config | 2 | M | P1 | F1-WP03 | `just test` runs unit + db tests locally and in CI |
| X2-WP02 | **Structural contracts:** `.importlinter`, `tests/structural/*` (no-order, deliberate-only, no-secrets, gateway-no-django) | 2 | M | P1 | F1-WP01 | Each contract fails when a deliberate violation is introduced (verified once, then reverted) |
| X2-WP03 | **CI workflow `ci.yml`:** lint, structural, py-unit, py-db (service containers), web-unit, caching of uv/pnpm | 3 | M | P1 | X2-WP01, X2-WP02 | Green on main; under 10 min |
| X2-WP04 | **Contract + WS tests:** drift check, round-trip fixtures, hypothesis fuzzing of client ops | 2 | S | P1 | F1-WP08, F1-WP04 | Changing a schema without regenerating fails CI |
| X2-WP05 | **Recorded fixtures:** curated Parquet recordings (1 trading day × 3 symbols) from P0, fixture loader, fake-gateway compose profile wiring for tests | 2 | S | P1 | P0-WP07, F2-WP06 | Fixtures load in < 2 s; fake gateway replays them deterministically |
| X2-WP06 | **Integration job:** `integration.yml` with compose offline profile, end-to-end assertions (bars persisted, signal emitted, WS frames received) | 4 | M | P2 | X2-WP05, P2-WP08 | Job green nightly; a broken ingestor makes it fail |
| X2-WP07 | **Playwright E2E + visual regression:** login → symbol page live chart → signal appears and resolves; chart screenshots on fixed fixtures | 3 | M | P2 | X2-WP06, P2-WP10 | E2E green; visual diffs reviewed on change |
| X2-WP08 | **Leakage suite:** all tests in 4.3, `leakage.yml` workflow | 4 | M | P3 | P3-WP01, P3-WP05, P3-WP09 | Suite green; bypassed-guard canary is detected |
| X2-WP09 | **Promotion gate:** `promote_model` command with the 4 checks, PromotionRecord, alias move + reload, failure reasons | 3 | M | P3 | P3-WP11, P3-WP13 | Promotion without holdout artifacts is refused; a successful promotion switches live inference |

**Totals:** P1 = 11 h · P2 = 7 h · P3 = 7 h

## 6. Testing

This plan *is* the testing plan. Its own correctness check: every contract and structural test is shown to **fail on a deliberate violation** once, in the PR that adds it.

## 7. Exit criteria

There is no master exit criterion for X2 itself. It supports every phase. Measurable checks:

- [ ] The four structural guarantees (no order code, MT5 only in the gateway, deliberate-only advisor, no secrets to the browser) are enforced in CI from Phase 1, with advisor rules active once X1 lands.
- [ ] CI runs fully without an MT5 terminal and without spending API tokens.
- [ ] The leakage suite and promotion gate are active before the first champion is promoted (P3).

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Flaky timing tests (WS, streams) | Deterministic fake-gateway clock. Assert on eventual state with timeouts, not sleeps |
| Slow CI from Timescale/compose | Split jobs. Integration runs on PRs to main and nightly, not every push |
| Structural tests bypassed by dynamic imports (`importlib`) | The AST test also flags `importlib.import_module` / `__import__` with string literals containing `anthropic`, `sd_advisor` or `MetaTrader5` |

## 9. Open questions / verify at build time

- Whether import-linter's version supports the `include_external_packages` option and wildcard modules. If not, keep explicit lists, with the AST test as the backstop.
- Whether GitHub Actions minutes are needed. Everything can run locally with `just ci` if the repo stays private and offline.
