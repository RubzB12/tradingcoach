---
paths:
  - "packages/sd_features/**"
  - "packages/sd_labeling/**"
  - "packages/sd_models/**"
  - "packages/sd_backtest/**"
  - "apps/fm_worker/**"
  - "apps/backend/signals/**"
  - "apps/backend/mlops/**"
  - "research/**"
---

# ML and validation rules (honest results first)

Leakage and overfitting are the main way this project can fool itself. Treat any surprisingly good result as a leakage bug until proven otherwise.

## Features and labels

- Every feature function takes `cutoff` and uses only rows with `time <= cutoff`. Register it in the `FEATURES` registry so the cutoff-compliance test covers it automatically.
- Higher-timeframe joins are as-of joins on bar **close** time (`join_asof`, strategy backward). Never join on bar open time.
- HMM regimes use **filtered** probabilities only (forward pass up to t). Never use `predict`/`predict_proba` over a full sequence, because that is smoothed and uses the future.
- Triple-barrier labels use ATR units at the event bar, the same multipliers as the policy's SL/TP. Intrabar ambiguity is **SL-first**, matching `barrier_sim` and the paper tracker.
- Use side-specific labels (long and short models), so that `P(up)` = P_long(tp) and `P(down)` = P_short(tp).

## Validation

- Every CV uses **purging + embargo**. Never use plain k-fold on overlapping labels. Walk-forward retraining is weekly, matching live.
- The frozen holdout (last 3–6 months) is reachable only through `load_dataset(final_eval=True)`, which only `promote_model` calls. Never pass it anywhere else, including notebooks.
- Calibrate (isotonic) on purged out-of-fold predictions only. Stacking meta-learners train on OOF predictions only.
- Log **every** Optuna trial and rule sweep to MLflow, because the trial count feeds the deflated Sharpe ratio.

## Reporting

- Always report at **1×, 1.5× and 2× costs**: spread, slippage, swap including the triple day, and commission. If the edge disappears at 1.5×, say so.
- Never optimise for or headline hit rate alone. Use expectancy (R), DSR, Brier/log loss, calibration and PBO.
- Negative results are valid outcomes. Write them up in `docs/reports/`, and don't keep tuning until something passes.

## Models and boundaries

- Models implement the `SignalModel` protocol (`fit`, `predict_proba` → `[P(up), P(down), P(timeout)]`, `explain`, optional `forecast`).
- Foundation and deep models are **features and visuals** until they beat the champion through the promotion gate (DSR and Brier on the frozen holdout).
- `research/` notebooks may import `packages/*`, but app code never imports `research/`.
- Never evaluate Claude's advice on historical data. Forward-only (look-ahead risk).

See: `docs/plans/P3-ml-and-explainability.md` §4, `docs/plans/P4-deep-learning-foundation-models.md` §4, `docs/plans/X2-testing-quality-governance.md` §4.3, §4.6.
