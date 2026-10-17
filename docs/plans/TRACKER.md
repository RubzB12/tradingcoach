# SignalDeck — Implementation Tracker

Status of every work package (WP) in [docs/plans](README.md), grouped by the phase it is **scheduled in** (foundation and cross-cutting WPs appear in the phase where they are built). The acceptance criteria in each WP's plan are its definition of done.

## How to update

- **Status values:** `todo` · `doing` · `done` · `blocked` · `deferred` (moved to a later phase, note where).
- When you start a WP: set `doing` and fill in **Started**. When its acceptance criteria pass: set `done`, fill in **Done** and **Actual h**, and add the commit/PR in **Notes**.
- When every `M` WP in a phase is `done` and the exit checks pass, tick the phase's exit box and update the summary table.
- With Claude Code: *"Implement P1-WP02 and update docs/plans/TRACKER.md when done."*

## Summary

| Phase | Master est. | WPs (M / S) | Est. h (M / total) | Done | Actual h | Exit met |
|---|---|---|---|---|---|---|
| [P0](#p0) | 1 wk | 7 / 0 | 12 / 12 | 0 / 7 | 0 | ☐ |
| [P1](#p1) | 3–4 wks | 34 / 7 | 88 / 100 | 0 / 41 | 0 | ☐ |
| [P2](#p2) | 4–5 wks | 22 / 3 | 76 / 82.5 | 0 / 25 | 0 | ☐ |
| [P3](#p3) | 5–7 wks | 26 / 0 | 96.5 / 96.5 | 0 / 26 | 0 | ☐ |
| [P4](#p4) | 4–6 wks | 12 / 1 | 55 / 58 | 0 / 13 | 0 | ☐ |
| [P5](#p5) | ongoing | 8 / 7 | 31.5 / 57 | 0 / 15 | 0 | ☐ |
| **Total** | | **127** | **359 / 406** | **0 / 127** | **0** | |

<a id="p0"></a>
## Phase 0 — Spike: MT5 connectivity

**Exit criterion (master):** *"24 h run without manual intervention."* — measurable checks in [P0-spike-mt5-connectivity.md §7](P0-spike-mt5-connectivity.md#7-exit-criteria).

- [ ] Exit criteria met — date: ____ — evidence: ____

| ID | Task | Pri | Est h | Actual h | Depends on | Status | Started | Done | Notes |
|---|---|---|---|---|---|---|---|---|---|
| [P0-WP01](P0-spike-mt5-connectivity.md#5-work-packages) | Terminal + broker demo | M | 1.5 |  | — | todo |  |  |  |
| [P0-WP02](P0-spike-mt5-connectivity.md#5-work-packages) | Python env + pin | M | 1.5 |  | P0-WP01 | todo |  |  |  |
| [P0-WP03](P0-spike-mt5-connectivity.md#5-work-packages) | Tick polling | M | 2 |  | P0-WP02 | todo |  |  |  |
| [P0-WP04](P0-spike-mt5-connectivity.md#5-work-packages) | UTC handling | M | 2 |  | P0-WP03 | todo |  |  |  |
| [P0-WP05](P0-spike-mt5-connectivity.md#5-work-packages) | Reconnect loop | M | 2 |  | P0-WP03 | todo |  |  |  |
| [P0-WP06](P0-spike-mt5-connectivity.md#5-work-packages) | Soak harness + analyzer | M | 2 |  | P0-WP05 | todo |  |  |  |
| [P0-WP07](P0-spike-mt5-connectivity.md#5-work-packages) | Tick recordings | M | 1 |  | P0-WP03 | todo |  |  |  |

<a id="p1"></a>
## Phase 1 — Data + live charts (incl. F1/F2/F3 foundations)

**Exit criterion (master):** *"Live chart latency <300 ms; gap-free M1 for watched symbols."* — measurable checks in [P1-data-and-live-charts.md §7](P1-data-and-live-charts.md#7-exit-criteria).

- [ ] Exit criteria met — date: ____ — evidence: ____

| ID | Task | Pri | Est h | Actual h | Depends on | Status | Started | Done | Notes |
|---|---|---|---|---|---|---|---|---|---|
| [F1-WP01](F1-backend-platform-django.md#5-work-packages) | Repo + toolchain bootstrap | M | 3 |  | P0 done | todo |  |  |  |
| [F1-WP02](F1-backend-platform-django.md#5-work-packages) | docker-compose infrastructure | M | 3 |  | F1-WP01 | todo |  |  |  |
| [F1-WP03](F1-backend-platform-django.md#5-work-packages) | Django skeleton | M | 3 |  | F1-WP02 | todo |  |  |  |
| [F1-WP04](F1-backend-platform-django.md#5-work-packages) | ASGI + Channels | M | 3 |  | F1-WP03 | todo |  |  |  |
| [F1-WP05](F1-backend-platform-django.md#5-work-packages) | Ninja API root | M | 2.5 |  | F1-WP03 | todo |  |  |  |
| [F1-WP06](F1-backend-platform-django.md#5-work-packages) | Celery | M | 2.5 |  | F1-WP02, F1-WP03 | todo |  |  |  |
| [F1-WP07](F1-backend-platform-django.md#5-work-packages) | Timescale helpers | M | 3 |  | F1-WP03 | todo |  |  |  |
| [F1-WP08](F1-backend-platform-django.md#5-work-packages) | Contract pipeline | M | 3 |  | F1-WP04, F1-WP05 | todo |  |  |  |
| [F1-WP09](F1-backend-platform-django.md#5-work-packages) | justfile + runbook | M | 1 |  | F1-WP01–F1-WP08 | todo |  |  |  |
| [F2-WP01](F2-mt5-gateway.md#5-work-packages) | Package + core loop | M | 3 |  | P0, F1-WP08 | todo |  |  |  |
| [F2-WP02](F2-mt5-gateway.md#5-work-packages) | Redis Streams publisher | M | 2.5 |  | F2-WP01 | todo |  |  |  |
| [F2-WP03](F2-mt5-gateway.md#5-work-packages) | Back-fill + bars | M | 3.5 |  | F2-WP02 | todo |  |  |  |
| [F2-WP04](F2-mt5-gateway.md#5-work-packages) | History service | M | 2.5 |  | F2-WP02 | todo |  |  |  |
| [F2-WP05](F2-mt5-gateway.md#5-work-packages) | Symbol catalog | M | 2 |  | F2-WP02 | todo |  |  |  |
| [F2-WP06](F2-mt5-gateway.md#5-work-packages) | Fake MT5 | M | 2.5 |  | F2-WP01–F2-WP05 | todo |  |  |  |
| [F2-WP07](F2-mt5-gateway.md#5-work-packages) | Windows autostart + runbook | S | 1 |  | F2-WP01 | todo |  |  |  |
| [F2-WP08](F2-mt5-gateway.md#5-work-packages) | No-order enforcement | M | 1 |  | F2-WP01 | todo |  |  |  |
| [F3-WP01](F3-frontend-platform-nextjs.md#5-work-packages) | Scaffold | M | 3 |  | F1-WP01 | todo |  |  |  |
| [F3-WP02](F3-frontend-platform-nextjs.md#5-work-packages) | Proxy + auth | M | 2 |  | F3-WP01, F1-WP05 | todo |  |  |  |
| [F3-WP03](F3-frontend-platform-nextjs.md#5-work-packages) | Typed API + Query | M | 2 |  | F3-WP02, F1-WP08 | todo |  |  |  |
| [F3-WP04](F3-frontend-platform-nextjs.md#5-work-packages) | ws-client | M | 3 |  | F3-WP01, F1-WP04 | todo |  |  |  |
| [F3-WP05](F3-frontend-platform-nextjs.md#5-work-packages) | Zustand stores | M | 2 |  | F3-WP04 | todo |  |  |  |
| [F3-WP06](F3-frontend-platform-nextjs.md#5-work-packages) | Chart wrapper | M | 4 |  | F3-WP05 | todo |  |  |  |
| [F3-WP07](F3-frontend-platform-nextjs.md#5-work-packages) | System UX | S | 2 |  | F3-WP04 | todo |  |  |  |
| [F3-WP08](F3-frontend-platform-nextjs.md#5-work-packages) | Frontend test setup | S | 2 |  | F3-WP01 | todo |  |  |  |
| [X2-WP01](X2-testing-quality-governance.md#5-work-packages) | Test harness | M | 2 |  | F1-WP03 | todo |  |  |  |
| [X2-WP02](X2-testing-quality-governance.md#5-work-packages) | Structural contracts | M | 2 |  | F1-WP01 | todo |  |  |  |
| [X2-WP03](X2-testing-quality-governance.md#5-work-packages) | CI workflow `ci.yml` | M | 3 |  | X2-WP01, X2-WP02 | todo |  |  |  |
| [X2-WP04](X2-testing-quality-governance.md#5-work-packages) | Contract + WS tests | S | 2 |  | F1-WP08, F1-WP04 | todo |  |  |  |
| [X2-WP05](X2-testing-quality-governance.md#5-work-packages) | Recorded fixtures | S | 2 |  | P0-WP07, F2-WP06 | todo |  |  |  |
| [P1-WP01](P1-data-and-live-charts.md#5-work-packages) | marketdata models + migrations | M | 3 |  | F1-WP07 | todo |  |  |  |
| [P1-WP02](P1-data-and-live-charts.md#5-work-packages) | `ingest_streams` command | M | 3 |  | P1-WP01, F2-WP02 | todo |  |  |  |
| [P1-WP03](P1-data-and-live-charts.md#5-work-packages) | History back-fill | M | 3 |  | P1-WP02, F2-WP04 | todo |  |  |  |
| [P1-WP04](P1-data-and-live-charts.md#5-work-packages) | Parquet lake export | S | 2 |  | P1-WP01, F1-WP06 | todo |  |  |  |
| [P1-WP05](P1-data-and-live-charts.md#5-work-packages) | Ninja routes | M | 2.5 |  | P1-WP01, F1-WP05 | todo |  |  |  |
| [P1-WP06](P1-data-and-live-charts.md#5-work-packages) | `stream_fanout` + consumer wiring | M | 3 |  | F1-WP04, F2-WP02 | todo |  |  |  |
| [P1-WP07](P1-data-and-live-charts.md#5-work-packages) | Symbol picker + watchlist | M | 2.5 |  | F3-WP03, F3-WP07, P1-WP05 | todo |  |  |  |
| [P1-WP08](P1-data-and-live-charts.md#5-work-packages) | Symbol page live chart | M | 3.5 |  | F3-WP06, P1-WP06 | todo |  |  |  |
| [P1-WP09](P1-data-and-live-charts.md#5-work-packages) | Health banner + latency telemetry | M | 2 |  | F3-WP07, P1-WP06 | todo |  |  |  |
| [P1-WP10](P1-data-and-live-charts.md#5-work-packages) | Data-quality caveats UI | S | 1 |  | P1-WP08 | todo |  |  |  |
| [P1-WP11](P1-data-and-live-charts.md#5-work-packages) | Exit verification | M | 1.5 |  | all | todo |  |  |  |

<a id="p2"></a>
## Phase 2 — Indicator signals + backtesting + Ask Claude v1

**Exit criterion (master):** *"Paper tracker resolving signals; baseline reports after costs; Ask Claude working end-to-end within budget."* — measurable checks in [P2-indicator-signals-backtesting.md §7](P2-indicator-signals-backtesting.md#7-exit-criteria).

- [ ] Exit criteria met — date: ____ — evidence: ____

| ID | Task | Pri | Est h | Actual h | Depends on | Status | Started | Done | Notes |
|---|---|---|---|---|---|---|---|---|---|
| [F1-WP10](F1-backend-platform-django.md#5-work-packages) | Structured logging | S | 1.5 |  | F1-WP03 | todo |  |  |  |
| [F2-WP09](F2-mt5-gateway.md#5-work-packages) | Read-only account reader | M | 2 |  | F2-WP04 | todo |  |  |  |
| [X2-WP06](X2-testing-quality-governance.md#5-work-packages) | Integration job | M | 4 |  | X2-WP05, P2-WP08 | todo |  |  |  |
| [X2-WP07](X2-testing-quality-governance.md#5-work-packages) | Playwright E2E + visual regression | M | 3 |  | X2-WP06, P2-WP10 | todo |  |  |  |
| [P2-WP01](P2-indicator-signals-backtesting.md#5-work-packages) | `sd_features` v1 | M | 4 |  | P1 | todo |  |  |  |
| [P2-WP02](P2-indicator-signals-backtesting.md#5-work-packages) | Rule strategies | M | 4 |  | P2-WP01 | todo |  |  |  |
| [P2-WP03](P2-indicator-signals-backtesting.md#5-work-packages) | Cost model | M | 3 |  | P1-WP01 | todo |  |  |  |
| [P2-WP04](P2-indicator-signals-backtesting.md#5-work-packages) | Barrier simulator + metrics | M | 4 |  | P2-WP02, P2-WP03 | todo |  |  |  |
| [P2-WP05](P2-indicator-signals-backtesting.md#5-work-packages) | Adapters | S | 3 |  | P2-WP04 | todo |  |  |  |
| [P2-WP06](P2-indicator-signals-backtesting.md#5-work-packages) | `backtests` app | M | 3 |  | P2-WP04, F1-WP06 | todo |  |  |  |
| [P2-WP07](P2-indicator-signals-backtesting.md#5-work-packages) | Backtest UI | M | 4 |  | P2-WP06, F3-WP06 | todo |  |  |  |
| [P2-WP08](P2-indicator-signals-backtesting.md#5-work-packages) | `signals` app + dispatcher + inference v0 | M | 4 |  | P2-WP02, P2-WP06 | todo |  |  |  |
| [P2-WP09](P2-indicator-signals-backtesting.md#5-work-packages) | `paper` tracker | M | 4 |  | P2-WP08, F2-WP09 | todo |  |  |  |
| [P2-WP10](P2-indicator-signals-backtesting.md#5-work-packages) | Live signal feed UI | M | 4 |  | P2-WP08, P2-WP09 | todo |  |  |  |
| [P2-WP11](P2-indicator-signals-backtesting.md#5-work-packages) | Pipeline animation v1 | M | 4 |  | P2-WP08, F3-WP07 | todo |  |  |  |
| [P2-WP12](P2-indicator-signals-backtesting.md#5-work-packages) | Indicator panes | M | 2 |  | P2-WP01, P1-WP08 | todo |  |  |  |
| [P2-WP13](P2-indicator-signals-backtesting.md#5-work-packages) | Backtest replay scrubber | S | 2 |  | P2-WP07 | todo |  |  |  |
| [P2-WP14](P2-indicator-signals-backtesting.md#5-work-packages) | Baseline report | M | 2 |  | P2-WP06 | todo |  |  |  |
| [X1-WP01](X1-ask-claude-advisor.md#5-work-packages) | sd_advisor scaffolding | M | 3 |  | F1-WP01 | todo |  |  |  |
| [X1-WP02](X1-ask-claude-advisor.md#5-work-packages) | Packet builder v1 | M | 4 |  | P2-WP01, P2-WP08, F2-WP09 | todo |  |  |  |
| [X1-WP03](X1-ask-claude-advisor.md#5-work-packages) | Client wrapper | M | 3 |  | X1-WP01 | todo |  |  |  |
| [X1-WP04](X1-ask-claude-advisor.md#5-work-packages) | Cost + budget + reuse | M | 2.5 |  | X1-WP01 | todo |  |  |  |
| [X1-WP05](X1-ask-claude-advisor.md#5-work-packages) | `advisor` Django app | M | 4 |  | X1-WP02–X1-WP04, F1-WP05 | todo |  |  |  |
| [X1-WP06](X1-ask-claude-advisor.md#5-work-packages) | Frontend v1 | M | 6 |  | X1-WP05, F3-WP03 | todo |  |  |  |
| [X1-WP07](X1-ask-claude-advisor.md#5-work-packages) | Advisor tests v1 | M | 2.5 |  | X1-WP05 | todo |  |  |  |

<a id="p3"></a>
## Phase 3 — ML + explainability + Ask Claude v2

**Exit criterion (master):** *"OOS (walk-forward) expectancy > 0 at 1.5× costs on ≥1 group, or documented negative result."* — measurable checks in [P3-ml-and-explainability.md §7](P3-ml-and-explainability.md#7-exit-criteria).

- [ ] Exit criteria met — date: ____ — evidence: ____

| ID | Task | Pri | Est h | Actual h | Depends on | Status | Started | Done | Notes |
|---|---|---|---|---|---|---|---|---|---|
| [X2-WP08](X2-testing-quality-governance.md#5-work-packages) | Leakage suite | M | 4 |  | P3-WP01, P3-WP05, P3-WP09 | todo |  |  |  |
| [X2-WP09](X2-testing-quality-governance.md#5-work-packages) | Promotion gate | M | 3 |  | P3-WP11, P3-WP13 | todo |  |  |  |
| [P3-WP01](P3-ml-and-explainability.md#5-work-packages) | Feature set v2 | M | 8 |  | P2-WP01 | todo |  |  |  |
| [P3-WP02](P3-ml-and-explainability.md#5-work-packages) | Triple-barrier labels | M | 4 |  | P3-WP01 | todo |  |  |  |
| [P3-WP03](P3-ml-and-explainability.md#5-work-packages) | Sample weights | M | 3 |  | P3-WP02 | todo |  |  |  |
| [P3-WP04](P3-ml-and-explainability.md#5-work-packages) | Meta-labeling | M | 3 |  | P3-WP02, P2-WP02 | todo |  |  |  |
| [P3-WP05](P3-ml-and-explainability.md#5-work-packages) | Validation splitters | M | 5 |  | P3-WP02 | todo |  |  |  |
| [P3-WP06](P3-ml-and-explainability.md#5-work-packages) | Training pipeline | M | 6 |  | P3-WP03, P3-WP05, F1-WP02 | todo |  |  |  |
| [P3-WP07](P3-ml-and-explainability.md#5-work-packages) | Calibration | M | 3 |  | P3-WP06 | todo |  |  |  |
| [P3-WP08](P3-ml-and-explainability.md#5-work-packages) | Metrics v2 | M | 3 |  | P3-WP06 | todo |  |  |  |
| [P3-WP09](P3-ml-and-explainability.md#5-work-packages) | HMM regimes | M | 4 |  | P3-WP01 | todo |  |  |  |
| [P3-WP10](P3-ml-and-explainability.md#5-work-packages) | Policy v1 + θ tuning | M | 4 |  | P3-WP07 | todo |  |  |  |
| [P3-WP11](P3-ml-and-explainability.md#5-work-packages) | `mlops` app | M | 4 |  | P3-WP06 | todo |  |  |  |
| [P3-WP12](P3-ml-and-explainability.md#5-work-packages) | Inference v2 | M | 4 |  | P3-WP10, P3-WP11 | todo |  |  |  |
| [P3-WP13](P3-ml-and-explainability.md#5-work-packages) | Walk-forward report generator | M | 4 |  | P3-WP08 | todo |  |  |  |
| [P3-WP14](P3-ml-and-explainability.md#5-work-packages) | SHAP UI | M | 4 |  | P3-WP12, F3-WP01 | todo |  |  |  |
| [P3-WP15](P3-ml-and-explainability.md#5-work-packages) | Confidence gauge + reliability badge | M | 2.5 |  | P3-WP12 | todo |  |  |  |
| [P3-WP16](P3-ml-and-explainability.md#5-work-packages) | Model-thinking stepper | M | 3 |  | P3-WP12 | todo |  |  |  |
| [P3-WP17](P3-ml-and-explainability.md#5-work-packages) | Regime overlay + pipeline v2 | M | 3.5 |  | P3-WP09, P2-WP11 | todo |  |  |  |
| [P3-WP18](P3-ml-and-explainability.md#5-work-packages) | Models page | M | 3.5 |  | P3-WP13 | todo |  |  |  |
| [P3-WP19](P3-ml-and-explainability.md#5-work-packages) | Exit evaluation + write-up | M | 2 |  | all | todo |  |  |  |
| [X1-WP08](X1-ask-claude-advisor.md#5-work-packages) | Packet v2 | M | 2.5 |  | P3-WP12, P3-WP13 | todo |  |  |  |
| [X1-WP09](X1-ask-claude-advisor.md#5-work-packages) | Modes v2 | M | 4 |  | X1-WP08, P2-WP09 | todo |  |  |  |
| [X1-WP10](X1-ask-claude-advisor.md#5-work-packages) | Evidence links + Show on chart | M | 3.5 |  | X1-WP06, F3-WP06 | todo |  |  |  |
| [X1-WP11](X1-ask-claude-advisor.md#5-work-packages) | Paper-tracking + agreement analytics | M | 4 |  | X1-WP05, P2-WP09 | todo |  |  |  |
| [X1-WP12](X1-ask-claude-advisor.md#5-work-packages) | Follow-up threads | M | 2 |  | X1-WP05 | todo |  |  |  |

<a id="p4"></a>
## Phase 4 — Deep learning, foundation models, ensembles

**Exit criterion (master):** *"Ensemble beats LightGBM champion on deflated Sharpe/Brier, else keep champion."* — measurable checks in [P4-deep-learning-foundation-models.md §7](P4-deep-learning-foundation-models.md#7-exit-criteria).

- [ ] Exit criteria met — date: ____ — evidence: ____

| ID | Task | Pri | Est h | Actual h | Depends on | Status | Started | Done | Notes |
|---|---|---|---|---|---|---|---|---|---|
| [P4-WP01](P4-deep-learning-foundation-models.md#5-work-packages) | fm-worker service | M | 4 |  | P3 | todo |  |  |  |
| [P4-WP02](P4-deep-learning-foundation-models.md#5-work-packages) | Forecast API + live path | M | 5 |  | P4-WP01 | todo |  |  |  |
| [P4-WP03](P4-deep-learning-foundation-models.md#5-work-packages) | Historical precompute + FM features | M | 5 |  | P4-WP02 | todo |  |  |  |
| [P4-WP04](P4-deep-learning-foundation-models.md#5-work-packages) | FM evaluation | M | 4 |  | P4-WP03 | todo |  |  |  |
| [P4-WP05](P4-deep-learning-foundation-models.md#5-work-packages) | Fan-chart primitive | M | 5 |  | P4-WP02, F3-WP06 | todo |  |  |  |
| [P4-WP06](P4-deep-learning-foundation-models.md#5-work-packages) | FM ablation explanations | M | 3 |  | P4-WP05 | todo |  |  |  |
| [P4-WP07](P4-deep-learning-foundation-models.md#5-work-packages) | neuralforecast models | M | 6 |  | P4-WP01, P3-WP05 | todo |  |  |  |
| [P4-WP08](P4-deep-learning-foundation-models.md#5-work-packages) | DL explainability | M | 5 |  | P4-WP07 | todo |  |  |  |
| [P4-WP09](P4-deep-learning-foundation-models.md#5-work-packages) | Stacking ensemble | M | 5 |  | P4-WP03, P4-WP07 | todo |  |  |  |
| [P4-WP10](P4-deep-learning-foundation-models.md#5-work-packages) | NautilusTrader replay | M | 6 |  | P3 | todo |  |  |  |
| [P4-WP11](P4-deep-learning-foundation-models.md#5-work-packages) | Prefect | M | 5 |  | P3-WP11 | todo |  |  |  |
| [P4-WP12](P4-deep-learning-foundation-models.md#5-work-packages) | Exit evaluation | M | 2 |  | P4-WP09 | todo |  |  |  |
| [P4-WP13](P4-deep-learning-foundation-models.md#5-work-packages) | FinCast experiment (stretch) | S | 3 |  | P4-WP04 | todo |  |  |  |

<a id="p5"></a>
## Phase 5 — Advanced + Ask Claude v3

**Exit criterion (master):** *"Drift alerts trigger challenger retrain automatically."* — measurable checks in [P5-advanced-monitoring-alerts.md §7](P5-advanced-monitoring-alerts.md#7-exit-criteria).

- [ ] Exit criteria met — date: ____ — evidence: ____

| ID | Task | Pri | Est h | Actual h | Depends on | Status | Started | Done | Notes |
|---|---|---|---|---|---|---|---|---|---|
| [P5-WP01](P5-advanced-monitoring-alerts.md#5-work-packages) | MTF confluence view | S | 5 |  | P3-WP01 | todo |  |  |  |
| [P5-WP02](P5-advanced-monitoring-alerts.md#5-work-packages) | Economic calendar | M | 6 |  | P3-WP10 | todo |  |  |  |
| [P5-WP03](P5-advanced-monitoring-alerts.md#5-work-packages) | News + sentiment | S | 6 |  | P4-WP01 (image) | todo |  |  |  |
| [P5-WP04](P5-advanced-monitoring-alerts.md#5-work-packages) | Portfolio view | M | 5 |  | P2-WP09 | todo |  |  |  |
| [P5-WP05](P5-advanced-monitoring-alerts.md#5-work-packages) | Drift monitoring | M | 6 |  | P3, P4-WP11 | todo |  |  |  |
| [P5-WP06](P5-advanced-monitoring-alerts.md#5-work-packages) | Drift → challenger retrain | M | 3 |  | P5-WP05, P5-WP07 | todo |  |  |  |
| [P5-WP07](P5-advanced-monitoring-alerts.md#5-work-packages) | Alert rules engine | M | 6 |  | P2-WP10 | todo |  |  |  |
| [P5-WP08](P5-advanced-monitoring-alerts.md#5-work-packages) | LLM explanations | S | 4 |  | P3-WP12 | todo |  |  |  |
| [X1-WP13](X1-ask-claude-advisor.md#5-work-packages) | Events/news in packet + opt-in web search | M | 3 |  | P5-WP02, P5-WP03 | todo |  |  |  |
| [X1-WP14](X1-ask-claude-advisor.md#5-work-packages) | Compare mode | S | 2.5 |  | X1-WP08 | todo |  |  |  |
| [X1-WP15](X1-ask-claude-advisor.md#5-work-packages) | Batch watchlist review | S | 3 |  | X1-WP05 | todo |  |  |  |
| [X1-WP16](X1-ask-claude-advisor.md#5-work-packages) | Invalidation → alert | M | 1.5 |  | P5-WP07 | todo |  |  |  |
| [X1-WP17](X1-ask-claude-advisor.md#5-work-packages) | Optional chart screenshot | S | 2 |  | X1-WP06 | todo |  |  |  |
| [X1-WP18](X1-ask-claude-advisor.md#5-work-packages) | "Claude agrees" meta-feature evaluation | S | 3 |  | X1-WP11, P3-WP11 | todo |  |  |  |
| [X1-WP19](X1-ask-claude-advisor.md#5-work-packages) | Prompt-injection test | M | 1 |  | X1-WP13 | todo |  |  |  |

## Decisions and blockers log

| Date | WP / plan | Decision or blocker | Outcome |
|---|---|---|---|
|  |  |  |  |
