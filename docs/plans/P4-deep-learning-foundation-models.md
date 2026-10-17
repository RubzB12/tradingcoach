# P4 — Deep Learning, Foundation Models, Ensembles

> **Type:** Phase · **Master effort:** 4–6 wks · **This plan:** 55 h (+3 h stretch)
> **Master plan refs:** Roadmap Phase 4; §3 Layer 3 (deep learning, foundation models, finance-specific FM, ensembles); Key Finding 5; §5 visual #5 (fan chart); §6 (deep models, foundation models by ablation); §4 NautilusTrader, Prefect; Recommendation 4
> **Index:** [README](README.md)

## 1. Goal and context

This phase tries the heavier model families **without trusting them by default**:

- **Foundation models** (Chronos-2, TimesFM 2.5, Moirai 2.0) are used as **fan-chart sources and feature generators**.
- **Deep forecasters** (N-HiTS, PatchTST, TFT) provide quantile forecasts and attention-based "where the model looked" views.
- A **stacking ensemble** combines everything.

Nothing gets promoted unless it beats the P3 LightGBM champion on deflated Sharpe and Brier (master: published evidence shows TSFMs underperform gradient boosting on returns). This phase also adds realistic **NautilusTrader** replay and moves pipelines to **Prefect**.

## 2. Scope

**In:** fm-worker service, forecast storage/streaming, historical forecast precompute + features, FM evaluation, fan-chart primitive, FM ablation explanations, neuralforecast models, Captum/attention, stacking, Nautilus replay, Prefect DAGs, exit evaluation. FinCast is a stretch experiment.

**Out:** drift-triggered retrains (P5) and news features (P5).

## 3. Dependencies

- [P3](P3-ml-and-explainability.md) done: champion per group, validation framework, MLflow registry, frozen holdout.
- Optional: an NVIDIA GPU for precompute. Everything must still run CPU-only, with smaller models and a coarser stride.

## 4. Design

### 4.1 `fm-worker` service

- New uv project `apps/fm_worker` (import `sd_fm`) with **its own container image** (PyTorch, `chronos-forecasting`, `timesfm`, `uni2ts`, `neuralforecast`, `captum`), so heavy and conflicting dependencies stay out of the backend image.
- It runs as a Celery worker on queue **`fm`**. It imports `sd_core`, `sd_contracts`, `sd_features`, and never Django. It writes forecasts through a small backend endpoint or straight to Redis + Postgres via `sd_core.db`.
- A model cache volume `data/hf-cache`. Each model loads lazily once per worker.

| Model | Variant (default) | Notes |
|---|---|---|
| Chronos-2 | base (120M); small (28M) on CPU | Native covariates, 8192 context |
| TimesFM 2.5 | 200M | 16k context, Apache-2.0 weights |
| Moirai 2.0 | small/base | Decoder-only |
| TimesFM 3.0 | optional | **Non-commercial weights** — fine for personal use; record the license in the MLflow run |
| TTM (Tiny Time Mixers) | optional | Only model to beat Log-HAR in the cited vol study; try it for volatility |

### 4.2 Forecast interface and storage

- Implements the `SignalModel.forecast(context) -> Quantiles` interface: input is the last `context_len` closes (log returns) + optional covariates; output is p10/p50/p90 (and p05/p95) for `h` steps.
- Table `forecast` (hypertable on `issued_at`): `symbol`, `tf`, `model_key`, `issued_at` (bar close), `horizon`, `context_len`, `quantiles` (jsonb: step → {p05…p95} in **log-return space**), `latency_ms`.
- Live path: `bar_close_dispatcher` → Celery `fm.forecast(symbol, tf, bar_time)` for watched symbols on H1 (configurable) → `forecast` row + `XADD forecast:{symbol}:{tf}` → fan-out → WS `forecast` channel.
- **Historical precompute** (`fm.precompute`): rolling-origin forecasts over the training range with a stride (default every 4 bars on H1), batched, written to `data/lake/forecasts/model=…/symbol=…/tf=…/`.
  - **Cutoff contract:** a forecast issued at t uses context ≤ t only.

### 4.3 FM-derived features and evaluation

- Features (added to the `sd_features` registry, as-of joined on `issued_at`):
  - `fm_ret_p50/ATR`
  - `fm_iqr/ATR` (implied vol)
  - `fm_skew = ((p90−p50) − (p50−p10))/ATR`
  - `fm_agree` (sign agreement across FMs)
- **Evaluation** (`sd_backtest.fm_eval`):
  - pinball loss / CRPS vs naive baselines (random walk, rolling empirical quantiles)
  - directional accuracy of p50
  - volatility forecast vs **Log-HAR**
  - per horizon and per symbol group, logged to MLflow
- Then: does adding FM features to LightGBM improve WF OOS log loss, expectancy at 1.5× and DSR? It is promoted only through the standard governance gate.

### 4.4 Deep forecasters (`neuralforecast`)

- N-HiTS, PatchTST and TFT with quantile loss (`MQLoss`), plus exogenous features (subset of the registry). Walk-forward with a **monthly** retrain cadence because of cost. Each run is logged to MLflow.
- Outputs:
  - (a) quantile features (as for FMs)
  - (b) `P(r_h > +x·ATR)` and `P(r_h < −x·ATR)` from the quantile distribution, used as stacking inputs

  This is documented as an approximation: it is not path-dependent like barrier probabilities.
- LSTM/GRU baseline for reference (optional, cheap).

### 4.5 Explainability for deep and FM models (§6)

- **TFT:** variable-selection weights + interpretable attention. If neuralforecast does not expose them cleanly, use PyTorch Forecasting's TFT for this view (verify at build time).
- **N-HiTS/PatchTST:** Captum Integrated Gradients over the input window gives per-timestep attributions.
- **UI:** `AttentionHeatmap` pane aligned under candles, labelled **"where the model looked"**, with the caveat *attention ≠ explanation*.
- **Foundation models, explained by ablation:** forecast with vs without the last N bars, and with vs without covariates. The fan chart shows the delta (ghost band).

### 4.6 Fan chart (§5 visual #5)

- `FanChart` series primitive (registered in F3's chart-core): draws the p10–p90 (and p05–p95, lighter) bands and the p50 line **ahead of the last bar**, using whitespace future time points.
- **Morphing:** quantiles are stored as log-returns, so on each tick the band is re-anchored to the live price, with a Motion-tweened transition when a new forecast arrives.
- Overlays the current signal's triple-barrier box (TP/SL/expiry) on the same pane.
- Model selector: Chronos-2 / TimesFM / Moirai / DL / ensemble.

### 4.7 Stacking ensemble (`sd_models.ensemble`)

- **Inputs:** purged walk-forward OOF calibrated probabilities from the LightGBM champion, the meta-label model, DL-derived probabilities, and the LightGBM+FM-features variant.
- **Meta-learner:** logistic regression (L2) trained on OOF only, then isotonic recalibration.
- **Alternative:** regime-conditional weighting (weights per HMM state from OOF performance).
- **Ensemble dispersion** = std across members. It feeds the confidence gauge's jitter.
- Registered as a challenger under the same group/tf name, so the comparison page shows champion vs ensemble.

### 4.8 NautilusTrader replay

- `sd_backtest.adapters.nautilus`: loads bars/ticks from the lake into a `BacktestEngine` with a venue config (fill model, latency model, spread from ticks, commissions), and replays the champion/ensemble decisions as a Nautilus `Strategy`.
- **Simulated orders exist only inside Nautilus's simulator.** The live adapters are never installed or imported. An import-linter rule forbids `nautilus_trader.adapters`, and the MT5 no-order rule is unchanged.
- Reconciliation report: Nautilus vs `barrier_sim` expectancy and trade-level differences. Large gaps mean the bar simulator is too optimistic.

### 4.9 Prefect

- Compose adds `prefect-server` (with its own Postgres DB) and `prefect-worker`, running the backend image with `django.setup()` so flows can update the `mlops` mirror.
- **Flows:**
  - `retrain_group` (download/refresh lake → features → train → evaluate → WF report → register challenger). This replaces the P3 Celery beat retrain.
  - `fm_precompute`
  - `dl_retrain_monthly`
  - `nautilus_replay`
- Celery remains for app-facing jobs (backtests from the UI, inference, lake export). **Rule of thumb:** Prefect for DAGs, Celery for request-driven work.

## 5. Work packages

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| P4-WP01 | **fm-worker service:** `apps/fm_worker` project, Dockerfile (CPU default, CUDA variant), Celery `fm` queue, HF cache volume, lazy model loading | 4 | M | P3 | Worker starts and loads Chronos-2 small on CPU, and a health task responds |
| P4-WP02 | **Forecast API + live path:** `forecast` hypertable, `fm.forecast` task for Chronos-2/TimesFM 2.5/Moirai 2.0, dispatcher hook, Redis + WS `forecast` channel, contracts | 5 | M | P4-WP01 | Forecasts arrive on the symbol page within 10 s of H1 close (CPU) |
| P4-WP03 | **Historical precompute + FM features:** rolling-origin batched precompute to lake, cutoff tests, FM features in registry | 5 | M | P4-WP02 | 2 yrs H1 × watched symbols precomputed; cutoff test for FM features passes |
| P4-WP04 | **FM evaluation:** pinball/CRPS vs naive, directional, vol vs Log-HAR, optional TTM; MLflow logging; `docs/reports/p4-fm-eval.md` | 4 | M | P4-WP03 | Report compares every FM against the baselines per horizon |
| P4-WP05 | **Fan-chart primitive:** bands + p50 ahead of last bar, tick re-anchoring, tweened updates, barrier box overlay, model selector | 5 | M | P4-WP02, F3-WP06 | Fan updates smoothly; band re-anchors with live price |
| P4-WP06 | **FM ablation explanations:** with/without last N bars and covariates; ghost band delta in UI | 3 | M | P4-WP05 | Toggling ablation shows a visible delta and a numeric summary |
| P4-WP07 | **neuralforecast models:** N-HiTS/PatchTST/TFT with MQLoss + exogenous, monthly WF, MLflow, quantile features + derived probabilities | 6 | M | P4-WP01, P3-WP05 | WF OOS metrics logged for all three on ≥ 1 group |
| P4-WP08 | **DL explainability:** TFT variable selection/attention, Captum IG for N-HiTS/PatchTST, `AttentionHeatmap` pane with caveat label | 5 | M | P4-WP07 | Heatmap aligns with candle times; caveat label visible |
| P4-WP09 | **Stacking ensemble:** OOF-only logistic meta-learner + recalibration, regime-conditional variant, dispersion, challenger registration, ensemble-vs-champion comparison page | 5 | M | P4-WP03, P4-WP07 | Comparison page shows DSR, Brier, expectancy at 1/1.5/2× for champion vs ensemble |
| P4-WP10 | **NautilusTrader replay:** adapter, venue/fill/latency config, strategy replay of decisions, reconciliation vs `barrier_sim`, import-linter rule against live adapters | 6 | M | P3 | Reconciliation report exists; differences explained |
| P4-WP11 | **Prefect:** compose services, flows (`retrain_group`, `fm_precompute`, `dl_retrain_monthly`, `nautilus_replay`), deployments + schedules, retire Celery retrain beat | 5 | M | P3-WP11 | Weekly retrain runs from Prefect and registers a challenger |
| P4-WP12 | **Exit evaluation:** frozen-holdout comparison (DSR, Brier) ensemble vs champion via `promote_model`; decision record `docs/decisions/00xx-p4-ensemble.md` | 2 | M | P4-WP09 | Decision recorded either way |
| P4-WP13 | **FinCast experiment (stretch):** 1B model zero-shot on one group; treat author-reported gains skeptically; compare in the FM eval report | 3 | S | P4-WP04 | Results appended to `p4-fm-eval.md` |

**Total:** 55 h must-have + 3 h stretch = **58 h ≈ 5–6 weeks** (within the master's 4–6 weeks).

## 6. Testing (see [X2](X2-testing-quality-governance.md))

- Cutoff compliance for FM and DL features (forecast at t never uses data after t).
- Ensemble trained strictly on OOF: a test asserts no in-sample member predictions are used.
- Import-linter: no `nautilus_trader.adapters.*`; `sd_fm` never imports Django.
- Fan-chart visual regression with fixture quantiles.

## 7. Exit criteria

**Master:** *"Ensemble beats LightGBM champion on deflated Sharpe/Brier, else keep champion."*

Measurable checks:

- [ ] On the frozen holdout for ≥ 1 group/tf: the ensemble's DSR > the champion's DSR **and** its Brier ≤ the champion's Brier → promote via `promote_model`. Otherwise the champion stays and the decision record says why.
- [ ] FM evaluation report published, including any case where FMs lose to naive baselines.
- [ ] Master deliverables present: fan-chart primitive, ensemble-vs-champion comparison, attention heatmaps.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Compute cost of precompute on CPU | Use small variants, stride ≥ 4, watched symbols only, cache in the lake. Optionally rent a GPU just for precompute |
| Dependency conflicts (torch, numpy, lightgbm) | Separate fm-worker image and uv project |
| Shiny visuals mistaken for edge | Every FM/DL view shows its eval badge (pinball vs naive). Promotion only via the governance gate |
| Nautilus API churn | Pin the version and isolate it behind the adapter |

## 9. Open questions / verify at build time

- Package names, versions and APIs: `chronos-forecasting` (Chronos-2 support), `timesfm` (2.5 API), `uni2ts` (Moirai 2.0), `neuralforecast` (TFT interpretability exposure), NautilusTrader current release.
- GPU availability on this machine.
