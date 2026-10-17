# P3 — ML + Explainability (+ Ask Claude v2)

> **Type:** Phase · **Master effort:** 5–7 wks · **This plan:** 73.5 h own + 23 h cross-cutting = **96.5 h** (see §5 budget)
> **Master plan refs:** Roadmap Phase 3; §3 Layers 1–5; §4 validation protocol, metrics, experiment tracking; §5 visuals #2–#4, #6; §6 Explainability (tree models); Recommendations 4, 5, 7; §7 Ask Claude v2
> **Index:** [README](README.md)

## 1. Goal and context

This phase replaces "rule fires → signal" with **calibrated probabilities from LightGBM** trained on triple-barrier labels. It is validated with purged/embargoed CV, walk-forward and deflated Sharpe, and explained per signal with SHAP, regime and EV breakdowns.

Honest validation comes first. The phase succeeds either by finding a cost-robust OOS edge on at least one symbol group **or by documenting a credible negative result**.

## 2. Scope

**In:**
- Phase-specific WPs below
- [X1](X1-ask-claude-advisor.md) v2 (WP08–WP12)
- [X2](X2-testing-quality-governance.md) WP08 (leakage suite) and WP09 (governance)

**Out:**
- Deep learning, foundation models and stacking ensembles (P4)
- Drift monitoring (P5)
- Prefect DAGs (P4). In P3, training is driven by management commands and Celery.

## 3. Dependencies

- [P2](P2-indicator-signals-backtesting.md) done: features v1, cost model, simulator, signal ledger and paper tracker.
- Enough history: ≥ 3 years of H1 and ≥ 1 year of M15 per symbol in the lake, if the broker provides it.

## 4. Design

### 4.1 Layer 1 — Features (`sd_features` v2)

All features are computed in Polars under the `cutoff` contract and registered in a `FEATURES` registry with name, group and params. That registry lets SHAP output map back to readable names.

| Group | Features |
|---|---|
| Returns | log returns over 1, 3, 6, 12, 24 bars |
| Volatility | Parkinson, Garman–Klass (20, 60), ATR(14)/close, vol-of-vol |
| Distances | (close − EMA20/50/200)/ATR, distance to 20/60-bar high/low in ATR, distance to the prior day's high/low/close |
| Momentum | RSI(14) + 3-bar slope, MACD hist + slope, Stoch %K/%D slope, ADX + DI spread |
| Bar shape | range/ATR, upper/lower wick ratio, body ratio, gap from previous close |
| Costs | spread/ATR (current and 20-bar mean) |
| Calendar | sin/cos hour-of-day, day-of-week, session flags (Asia/London/NY), minutes to session close |
| HTF context | H4/D1 trend state (EMA stack sign, ADX bucket) joined **as-of the decision bar close** (`join_asof`, strategy=backward, on bar *close* time) |
| Cross-asset (FX) | DXY proxy (equal-weight USD vs majors from watched pairs), risk-on proxy (AUDJPY return) |
| Stationarity | fractionally differentiated log close (d chosen per symbol by min ADF-passing d, fixed-width window) |
| Regime (from 4.5) | HMM filtered state probabilities |

### 4.2 Layer 2 — Labels (`sd_labeling`)

- `triple_barrier(bars, events, pt_mult, sl_mult, max_hold, side, atr)`. The barrier unit is **ATR(14) at the event bar**, the same unit the policy uses for SL/TP (master: "the same multiplier as the label barrier").
  - Output: `label ∈ {+1 (tp first), −1 (sl first), 0 (timeout)}`, `t1` (exit time) and `ret_R`.
  - Intrabar ambiguity is resolved **SL-first**, matching `barrier_sim`.
- **Events:**
  - Direction models use CUSUM-filtered bars (threshold = k·ATR).
  - Meta-labeling uses the P2 rule decisions.
- **Side-specific labels:** train a **long model** (long barriers) and a **short model** (short barriers), each 3-class. Define `P(up) := P_long(tp)` and `P(down) := P_short(tp)`. This keeps the EV math exact when `pt_mult ≠ sl_mult`.
- **Sample weights:** average uniqueness from label concurrency (`t0..t1` overlap counts), with optional return attribution and time decay.
- **Meta-labeling:** for each rule event, label = 1 if the rule's trade resolved with `R > 0`, else 0. A binary LightGBM gives P(rule is right), which drives take/skip and the confidence display.

### 4.3 Layer 3 — Models (`sd_models` v2)

- `LightGBMBarrierModel` (implements `SignalModel`): long and short multiclass boosters, feature list pinned, `predict_proba` returning `[P(up), P(down), P(timeout)]`, `explain` via SHAP.
- `MetaLabelModel`: a rule key + binary booster.
- **Fold ensemble for dispersion:** keep the K walk-forward fold models. *Agreement* = std of their calibrated P(side) at inference.
- **Symbol groups** (`Symbol.group`): e.g. `fx_majors`, `fx_jpy`, `stock_cfd_us`. There is one champion per group × tf.

### 4.4 Validation (`sd_backtest.validation`)

- **Holdout:** the last **4 months** (configurable 3–6) are frozen. `load_dataset()` refuses rows after `holdout_start` unless called with `final_eval=True` by `promote_model` (X2-WP09).
- **Purged k-fold + embargo** (5 folds, 5% embargo) for HPO. Purging removes training events whose `[t0, t1]` overlaps the test fold.
- **Walk-forward:** anchored and rolling, with **weekly retrain cadence** simulated over the pre-holdout period. This produces the OOS predictions used for calibration, θ tuning and all reported metrics.
- **CPCV** via `skfolio` (CombinatorialPurgedCV): gives the distribution of OOS Sharpe and the **probability of backtest overfitting (PBO)**.
- **Deflated Sharpe Ratio** with `n_trials` = the total count of Optuna trials + rule sweeps logged in MLflow for that group/tf.
- **HPO:** Optuna (storage `postgresql://…/optuna`, MedianPruner). The objective is mean purged-CV **log loss**. θ is tuned separately (4.6) on a cost-aware objective.

### 4.5 Regimes (`sd_models.regime`)

- `hmmlearn.GaussianHMM` with 2–4 states, chosen by BIC, on [log return, realized vol], fitted **inside each training window**.
- **Leakage guard:** at inference and for features, use **filtered** probabilities (forward pass up to t only). Do **not** use `predict`/`predict_proba` over the whole sequence, because that is smoothed and uses future data. Implement `filtered_proba(model, X_prefix)` using the forward algorithm. X2-WP08 tests that appending future rows does not change past probabilities.
- States are relabelled by mean volatility (calm < normal < turbulent), so names stay stable across refits. The transition matrix is exported for the UI.
- **Regime fit:** an OOS performance table per state. If the current state has < 200 training events or max posterior < 0.6, the UI shows a **"regime not seen in training"** warning.

### 4.6 Layers 4–5 — Calibration and policy

- **Isotonic calibration** is fitted on purged walk-forward OOF predictions, separately for each side's P(tp). Reported metrics: Brier, log loss, calibration slope/intercept, reliability bins (10).
- **Policy v1** (`signals.policy`):
  ```
  EV_long  = P_long(tp)·m_tp − P_long(sl)·m_sl + P_long(timeout)·E[R|timeout,long] − costs_R − swap_R
  BUY  if P(up) − P(down) > θ and EV_long  > 0      (symmetric for SELL)
  else HOLD
  entry = ask (buy) / bid (sell); SL = entry ∓ m_sl·ATR; TP = entry ± m_tp·ATR; expiry = max_hold bars
  suppress: cooldown, outside session, regime gate (optional per group), (P5: news windows)
  ```
- **θ tuning:** a grid on walk-forward OOS to maximize **expectancy at 1.5× costs** subject to ≥ N trades/month. Deflated Sharpe is reported alongside. **Never hit rate alone.**

### 4.7 MLOps (`mlops` app + MLflow)

- MLflow experiment per group/tf. Each run logs:
  - params
  - feature list + hash
  - data snapshot ID (lake partition range + sha)
  - CV/WF metrics at 1/1.5/2× costs
  - artifacts: reliability plot, SHAP global, fold-importance stability, WF report HTML, models
- Registered model `signaldeck-{group}-{tf}` with aliases **`champion`** / **`challenger`**.
- `ModelVersion` mirror table: `name`, `version`, `mlflow_run_id`, `alias`, `trained_until`, `wf_metrics`, `holdout_metrics`, `promoted_at`, `promoted_by_report`. `PromotionRecord` keeps the audit trail.
- **Inference** loads `models:/…@champion` once per worker and reloads on a Redis `mlops.reload` pub/sub message.
- Commands:
  - `train_group --group --tf`
  - `walkforward_report --group --tf`
  - `promote_model` (X2-WP09 gates)
- A weekly retrain runs as a Celery beat task in P3, and moves to Prefect in P4.

### 4.8 Explainability (§6 tree models)

- **Per signal:** `shap.TreeExplainer` on the chosen side's booster gives the top-8 features with value, SHAP value and base value. These are stored in `SignalExplanation`:
  - `shap_top`, `base_value`
  - `raw_probs`, `calibrated_probs`, `dispersion`
  - `regime` (state, probs, transition row)
  - `ev_breakdown`
  - `narration_steps`
  - `packet_version`
- **Global:** importance per fold, plus **stability** = mean Spearman rank correlation across folds. Flag < 0.5 as an overfitting red flag in the models page.
- **Explanation packet:** a deterministic JSON built in `signals.explain.build_packet(signal)`. It is the single source for the stepper, the template text and the X1 advisor packet.

### 4.9 Frontend

| Component | Content |
|---|---|
| `ShapWaterfall` (ECharts) | Base → features → output, value labels, click a bar → highlights that feature's pane if it exists |
| `RollingShap` | Stacked area of \|SHAP\| share by feature group over the last N signals (drift hint). `GET /signals/explanations/rolling` |
| `ConfidenceGauge` | Calibrated P(side) with a jitter animation proportional to fold dispersion. Reliability badge = live Brier (last 50 resolved) vs WF Brier |
| `ThinkingStepper` | 5–8 Motion-staggered steps from `narration_steps` (e.g. "Trend on H4 is up (ADX 31)" → "Volatility regime: calm" → "Top drivers…" → "P(up)=0.61 → calibrated 0.57" → "EV after 1.2-pip spread = +0.18R → BUY") |
| `RegimeBands` primitive | Background bands by HMM state + `TransitionMatrix` mini heatmap |
| Pipeline v2 | Regime → Models → Calibrate nodes enabled, showing intermediate outputs |
| Models page | Registry table (champion/challenger), reliability diagram, Brier/log loss, fold-importance stability, WF report (equity at 1/1.5/2×), CPCV Sharpe histogram + PBO, DSR, holdout results |
| Honesty badges (Rec. 7) | On every signal card: cost-adjusted live expectancy, calibration badge, "regime not seen" warning |

## 5. Work packages (phase-specific)

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| P3-WP01 | **Feature set v2:** all groups in 4.1, registry, as-of HTF join, DXY proxy, frac-diff | 8 | M | P2-WP01 | Cutoff-compliance test passes for every registered feature; feature matrix for 3 yrs H1 × 10 symbols builds in < 2 min |
| P3-WP02 | **Triple-barrier labels:** ATR-unit barriers, side-specific, SL-first ambiguity, `t1`/`ret_R` | 4 | M | P3-WP01 | Edge-case tests pass: gaps through barrier, timeout, simultaneous hit |
| P3-WP03 | **Sample weights:** concurrency + average uniqueness (+ optional time decay) | 3 | M | P3-WP02 | Matches a hand-computed small example |
| P3-WP04 | **Meta-labeling:** rule events → labels → binary model wiring | 3 | M | P3-WP02, P2-WP02 | Meta-model OOS AUC reported for each rule × group |
| P3-WP05 | **Validation splitters:** purged k-fold + embargo, walk-forward (anchored/rolling, weekly), CPCV via skfolio + PBO, holdout guard | 5 | M | P3-WP02 | Purging test: no train event overlaps a test window; holdout access raises without `final_eval` |
| P3-WP06 | **Training pipeline:** LightGBM long/short + Optuna (Postgres, pruning) + MLflow logging + registry registration; `train_group` command | 6 | M | P3-WP03, P3-WP05, F1-WP02 | One command trains and registers a group/tf model with all artifacts in MLflow |
| P3-WP07 | **Calibration:** isotonic on purged OOF per side, reliability bins, Brier/log loss/slope | 3 | M | P3-WP06 | Calibrated OOS reliability slope within [0.8, 1.2] on at least one group, or reported as failing |
| P3-WP08 | **Metrics v2:** deflated Sharpe (trial count from MLflow), calibration metrics, per-regime breakdown | 3 | M | P3-WP06 | DSR matches a published worked example |
| P3-WP09 | **HMM regimes:** BIC state selection, filtered probabilities, vol-ordered labels, transition matrix, regime-fit table, "unseen regime" rule | 4 | M | P3-WP01 | Future-invariance test passes (X2-WP08) |
| P3-WP10 | **Policy v1 + θ tuning:** EV formula, levels from barrier multipliers, suppressions, θ grid on cost-aware objective | 4 | M | P3-WP07 | θ per group stored on the ModelVersion; policy unit tests cover HOLD/BUY/SELL boundaries |
| P3-WP11 | **`mlops` app:** ModelVersion/PromotionRecord, champion loading + reload pub/sub, weekly retrain beat task, admin | 4 | M | P3-WP06 | Changing the alias in MLflow + `mlops.reload` switches inference without restart |
| P3-WP12 | **Inference v2:** features → model → calibrate → policy → SHAP top-8 → SignalExplanation → `explain:*` + pipeline events; rules remain as a separate `source=rule` track | 4 | M | P3-WP10, P3-WP11 | Model signals appear within 3 s of bar close, each with an explanation |
| P3-WP13 | **Walk-forward report generator:** per group/tf HTML+JSON (OOS expectancy at 1/1.5/2×, DSR, PBO, importance stability, per-regime) logged to MLflow | 4 | M | P3-WP08 | Report renders for every group; linked from the models page |
| P3-WP14 | **SHAP UI:** `ShapWaterfall` + `RollingShap` + rolling endpoint | 4 | M | P3-WP12, F3-WP01 | Waterfall sums to the model output; rolling chart updates on new signals |
| P3-WP15 | **Confidence gauge + reliability badge** | 2.5 | M | P3-WP12 | Jitter scales with dispersion; badge computes from live resolved signals |
| P3-WP16 | **Model-thinking stepper:** narration templates from explanation packet, staggered animation | 3 | M | P3-WP12 | Stepper text matches packet numbers exactly (snapshot test) |
| P3-WP17 | **Regime overlay + pipeline v2:** `RegimeBands` primitive, transition matrix, enable P3 nodes in PipelineGraph | 3.5 | M | P3-WP09, P2-WP11 | Bands align with bars; clicking Regime node shows state probabilities |
| P3-WP18 | **Models page:** registry, reliability diagram, stability, WF report embed, CPCV histogram, DSR, holdout | 3.5 | M | P3-WP13 | All master §4 metrics visible for the champion |
| P3-WP19 | **Exit evaluation + write-up:** `docs/reports/p3-walkforward.md` with results per group, including negative ones | 2 | M | all | Report states the exit verdict explicitly |

**Phase-specific total:** 73.5 h

### Phase budget (everything scheduled in P3)

| Source | WPs | Hours |
|---|---|---|
| P3 | WP01–WP19 | 73.5 |
| X1 (Ask Claude v2) | WP08–WP12 | 16 |
| X2 | WP08–WP09 | 7 |
| **Total** | | **96.5 h ≈ 8–9.5 weeks** |

> **Budget note:** the master range is 5–7 weeks (50–84 h). Feature engineering (WP01) and the UI WPs are the main things that could be cut. A lean path drops the cross-asset and frac-diff features at first, and the CPCV histogram UI (saves ≈ 6 h).

## 6. Testing (see [X2](X2-testing-quality-governance.md))

- **Leakage suite (X2-WP08):**
  - shifted-future canary feature → the cutoff guard must reject it; with the guard bypassed, the harness must detect the jump in OOS skill (this proves the test actually catches leaks)
  - label-permutation → ~0 skill
  - cutoff compliance for every feature
  - HMM future-invariance
- Labeling edge cases, weights, splitters (purge/embargo correctness), DSR worked example, policy boundaries.
- Governance (X2-WP09): `promote_model` refuses promotion without holdout comparison artifacts.

## 7. Exit criteria

**Master:** *"OOS (walk-forward) expectancy > 0 at 1.5× costs on ≥1 group, or documented negative result."*

Measurable checks:

- [ ] For ≥ 1 symbol group × tf: walk-forward OOS expectancy > 0 R at **1.5× costs** with ≥ 100 OOS trades, DSR reported, PBO < 0.5. **Or** `p3-walkforward.md` documents the negative result, covering what was tried, trial counts, and why it fails.
- [ ] Champion registered per group with MLflow run, WF report, calibration plot and cost sensitivity (master: model governance).
- [ ] Every model signal in the ledger has a SignalExplanation; the waterfall, gauge, stepper and regime overlay work live.
- [ ] `just test-leakage` green (local gate; there is no GitHub CI).
- [ ] Master deliverables present: champion model per symbol group, explanation packets, Claude-vs-model agreement panel (X1-WP11).

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Leakage through HTF joins, HMM smoothing, frac-diff windows, overlapping labels | Cutoff contract + as-of joins + filtered HMM + purging/embargo, each with a dedicated test |
| Overfitting via many trials | Every trial logged, DSR uses the total count, frozen holdout, CPCV/PBO |
| Too few events on M15/H1 for some symbols | Pool by symbol group. Report when trade counts are insufficient rather than tuning harder |
| Unstable feature importances | Stability metric shown, and it is used as a promotion consideration |

## 9. Open questions / verify at build time

- Library versions: LightGBM, shap (numpy-2 compatibility), skfolio CPCV API, hmmlearn maintenance status.
- Default barrier multipliers per group. Start with `m_tp = 2.0`, `m_sl = 1.0` ATR and `max_hold = 24` bars on H1, then tune within WF only.
- Group definitions depend on which symbols your broker demo offers.
