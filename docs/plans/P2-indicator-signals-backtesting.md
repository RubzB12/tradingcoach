# P2 — Indicator Signals + Backtesting (+ Paper Tracker, Ask Claude v1)

> **Type:** Phase · **Master effort:** 4–5 wks · **This plan:** 47 h own + 35.5 h cross-cutting = **82.5 h** (see §5 budget)
> **Master plan refs:** Roadmap Phase 2; §3 Layer 0 (indicators); §3 Layer 5 (signal policy, rule version); §4 backtesting stack, costs, metrics panel, live paper-tracking; §5 visuals #1 (pipeline v1), #7 (live feed), #8 (backtest replay); Recommendation 3 ("Build the paper tracker in Phase 2"); §7 Ask Claude v1
> **Index:** [README](README.md)

## 1. Goal and context

This phase gets the first explainable signals onto the screen and builds **honest measurement** in from the start:

- indicator features
- four rule strategies
- a cost model
- backtests with cost sensitivity
- a **signal ledger + live paper tracker**, the only metric that really matters
- the animated pipeline v1
- the live signal feed
- **Ask Claude v1**

The rule baselines become the bar that ML must beat after costs in P3.

## 2. Scope

**In:**
- Phase-specific WPs below
- [F1-WP10](F1-backend-platform-django.md#5-work-packages) logging
- [F2-WP09](F2-mt5-gateway.md#5-work-packages) read-only account reader
- [X1](X1-ask-claude-advisor.md) v1 (WP01–WP07)
- [X2](X2-testing-quality-governance.md) WP06–WP07

**Out:**
- ML models, calibration, SHAP and regimes (P3). The HMM "range regime" filter for RSI(2) uses ADX < 20 as a stand-in until P3.
- NautilusTrader (P4)
- News suppression (P5)

## 3. Dependencies

- [P1](P1-data-and-live-charts.md) exit criteria met: bars are gap-free and live channels work.

## 4. Design

### 4.1 Packages

**`sd_features` (v1):**

- `indicators.py` contains Polars-native wrappers over **TA-Lib 0.6.x**, with `pandas-ta-classic` as the fallback: EMA, SMA, RSI, MACD, ADX/DI, ATR, Bollinger (+ width), Donchian, Stochastic.
- Every function takes `(bars: pl.DataFrame, cutoff: datetime, **params)` and **must only use rows with `time <= cutoff`**. This is the "known-at-time t" contract; X2 tests it.
- `snapshot.py` builds the feature snapshot dict for a decision bar and computes `feature_hash = sha256(canonical_json(snapshot))`.

**`sd_models` (v1):**

- `base.py` defines the plug-in protocol used through P4:
  ```python
  class SignalModel(Protocol):
      key: str; version: str
      def fit(self, X, y, w=None) -> None: ...
      def predict_proba(self, X) -> np.ndarray: ...        # columns: P(up), P(down), P(timeout)
      def explain(self, X) -> list[Attribution]: ...       # optional
      def forecast(self, context) -> Quantiles | None: ... # optional (P4)
  class RuleStrategy(Protocol):
      key: str; params: dict
      def decide(self, bars, cutoff) -> RuleDecision | None  # side, reason codes, indicator values
  ```
- `rules/` holds the four baselines (defaults are tunable in backtests):

| Key | Logic | Levels |
|---|---|---|
| `ema_adx` | EMA(20) crosses EMA(50) **and** ADX(14) > 25 | SL = 1.5·ATR(14), TP = 2.5·ATR, expiry 24 bars |
| `rsi2_mr` | RSI(2) < 10 (buy) / > 90 (sell) **and** ADX < 20 (range proxy) **and** close above/below SMA(200) | SL = 1.0·ATR, TP = 1.0·ATR, expiry 8 bars |
| `donchian_breakout` | Close breaks the 20-bar Donchian high/low **and** ATR(14) > ATR median(100) | SL = 2.0·ATR, TP = 3.0·ATR, expiry 30 bars |
| `bb_squeeze` | BB width at its 120-bar low percentile < 10%, then close outside the band | SL = opposite band or 1.5·ATR, TP = 2·SL distance, expiry 20 bars |

**`sd_backtest` (v1):**

- `costs.py`: `CostModel(spread_points_series, slippage_mult=0.5, news_slippage_mult=1.0, commission_per_lot, swap_long, swap_short, rollover3days, point, contract_size)`.
  - Spread comes from the bar's MT5 `spread` column (a floor). Swap is charged per rollover crossed, ×3 on the triple-swap weekday.
  - Supports `scale` ∈ {1.0, 1.5, 2.0} for sensitivity analysis.
- `barrier_sim.py`: a bar-level simulator that applies **the same resolution rules as the paper tracker**:
  - entry at the next bar open ± half-spread
  - SL/TP checked on high/low
  - **SL-first if both are hit in one bar** (conservative)
  - expiry at the close of the expiry bar

  This parity is what makes the live-vs-backtest "implementation shortfall" chart meaningful.
- `metrics.py`: CAGR, Sharpe, Sortino, Calmar, max drawdown + duration, hit rate, profit factor, expectancy (R), average R:R, exposure, turnover, trade count. P3 adds Brier/log-loss/calibration/deflated Sharpe/per-regime.
- `adapters/vectorbt.py`: vectorized parameter sweeps (open-source vectorbt 0.26.x). Its results are only used for *exploration*. Reported numbers come from `barrier_sim` with costs.
- `adapters/backtesting_py.py`: single-symbol visual check, research only (AGPL — fine privately).

### 4.2 Django apps

**`signals`**

| Model | Fields |
|---|---|
| `Signal` | `id` (uuid), `symbol` FK, `tf`, `source` (rule\|model\|ensemble\|claude), `strategy_key`, `model_version` (str, nullable), `side` (buy\|sell), `status` (open\|tp\|sl\|expired\|cancelled), `bar_time`, `created_at`, `entry_ref`, `entry_fill`, `sl`, `tp`, `expiry_at`, `p_up`/`p_down`/`p_timeout` (nullable), `p_tp_empirical`, `confidence`, `ev_r`, `costs` (json), `feature_snapshot` (jsonb), `feature_hash`, `params` (json), `reason_codes` (json), `resolved_at`, `exit_price`, `r_multiple`, `slippage_r`, `mae_r`, `mfe_r`, `manual_fill` FK nullable |
| `StrategyConfig` | `strategy_key`, `symbol` FK (nullable = all watched), `tf`, `params`, `enabled`, `cooldown_bars` |

**Decision flow:**

```
ingest_streams ──(after commit) XADD bars.persisted {symbol, tf, time}
bar_close_dispatcher (cmd, consumer group "dispatcher") ─► Celery signals.tasks.run_inference(symbol, tf, bar_time)   [queue: ml]
run_inference:
  load last N bars (DB) → features(cutoff=bar_time) → for each enabled StrategyConfig: decide()
  → policy_v0: cooldown, session open (from SymbolSnapshot.sessions), spread sanity,
               EV = p_tp_emp·TP_R − (1−p_tp_emp)·1R − costs_R   (p_tp_emp from latest baseline backtest on this symbol/tf, Laplace-smoothed)
  → BUY/SELL if EV > 0 else HOLD
  → Signal row (if emitted) + XADD signals:{symbol} + XADD pipeline {stage events with timings and intermediate outputs}
```

`p_tp_empirical` is labelled **"historical hit rate (backtest)"** in the UI, never "probability". Real calibrated probabilities arrive in P3.

**`paper`**

- `paper_tracker` command (consumer group `paper` on `ticks:*`):
  - Keeps open signals in memory, refreshed from `signals:*`.
  - On each tick, checks:
    - **long:** entry fill = first ask after creation; exit if `bid <= sl` (fill at that bid → gap slippage), or `bid >= tp` (fill at tp)
    - **short:** mirror, using ask for exits
    - **expiry:** close at bid (long) or ask (short)
  - Computes the R multiple, entry/exit slippage in R, MAE/MFE and swap for nights held.
  - Persists the resolution, XADDs `signals:{symbol}` (resolution event) and invalidates stats.
  - **Catch-up on restart:** replays the `tick` table from the last processed `time_msc` for open signals.
- `ManualFillLink` (optional): links your manual demo trades to signals using F2-WP09 `history_deals_get` (symbol, side and time proximity).
- API `GET /paper/stats?symbol=&strategy=&since=` returns count, hit rate, expectancy R, avg R:R, live vs backtest expectancy (implementation shortfall).

**`backtests`**

- `BacktestRun`: `id`, `created_at`, `status`, `engine` (barrier_sim\|vectorbt), `params` (strategy, symbols, tf, period, strategy params), `cost_scales` [1, 1.5, 2], `metrics` (json keyed by scale), `artifact_dir` (`data/backtests/{id}/`: trades.parquet, equity.parquet), `error`.
- Celery `backtests.tasks.run_backtest(run_id)` on queue `backtest`. Progress goes to Redis `job:{id}` and the WS channel `job`.
- API:
  - `POST /backtests`
  - `GET /backtests`
  - `GET /backtests/{id}`
  - `GET /backtests/{id}/trades?page=`
  - `GET /backtests/{id}/equity?scale=1.5`

### 4.3 Frontend

- **Backtests:** a list + "New run" form; a detail page with:
  - a metrics panel (master §4 list)
  - an equity curve per cost scale
  - a drawdown chart
  - trade markers on candles
  - a **sensitivity table** with a red banner if expectancy ≤ 0 at 1.5×: *"If the edge disappears at 1.5×, it is not an edge"*
- **Backtest replay scrubber (S):** a timeline slider animating candles, trades and the equity curve in sync.
- **Live signal feed (`/signals` + side panel on the symbol page):** each `SignalCard` shows:
  - side, strategy, entry/SL/TP, R:R
  - historical hit rate, EV after costs
  - an expiry countdown
  - a live P&L in R

  It resolves live with a TP/SL/expiry animation. Feed extras:
  - Sonner toast on a new signal
  - browser notification if enabled
  - optional sound
  - per-symbol/strategy filters (stored in `UserSettings.notifications`)
- **SL/TP zones** are drawn on the price chart via a `BarrierBox` primitive (entry/SL/TP box ending at expiry).
- **Pipeline animation v1** (`components/pipeline/PipelineGraph`): nodes Tick → Bar close → Features → Rule → Costs/EV → Signal.
  - A packet animates through the nodes on each `pipeline` event.
  - Clicking a node shows its intermediate output (feature values, rule reason codes, EV math).
  - The nodes Regime → Models → Calibrate are shown greyed out as "Phase 3".
- **Indicator panes:** RSI, MACD and ADX panes on the symbol page. These replace the P1 placeholder and are computed server-side and served via `GET /bars/{name}/indicators?tf=&set=`.
- **Ask Claude v1** UI is specified in [X1](X1-ask-claude-advisor.md).

## 5. Work packages (phase-specific)

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| P2-WP01 | **`sd_features` v1:** TA-Lib/Polars indicator wrappers with `cutoff`, snapshot + hash, parity tests vs TA-Lib on fixtures | 4 | M | P1 | Parity within 1e-9 on fixtures; cutoff tests pass (X2) |
| P2-WP02 | **Rule strategies:** `SignalModel`/`RuleStrategy` protocols, 4 rules with reason codes + ATR levels, unit tests per rule on crafted series | 4 | M | P2-WP01 | Each rule fires and stays quiet on crafted up/down/range fixtures as expected |
| P2-WP03 | **Cost model:** spread floor, slippage multipliers, swap incl. triple day, commission, scale factor; tests | 3 | M | P1-WP01 | Hand-computed examples match, including the triple-swap Wednesday case |
| P2-WP04 | **Barrier simulator + metrics:** `barrier_sim` (parity rules), `metrics.py` (full v1 list), tests incl. SL-first ambiguity | 4 | M | P2-WP02, P2-WP03 | Metrics match a hand-computed 10-trade example |
| P2-WP05 | **Adapters:** vectorbt sweep (grid over rule params), backtesting.py single-symbol view; research notebook demonstrating both | 3 | S | P2-WP04 | Sweep of 100 param combos on 2 yrs H1 runs in < 60 s |
| P2-WP06 | **`backtests` app:** model, Celery task, progress events, artifacts, Ninja routes, cost sensitivity at 1/1.5/2× | 3 | M | P2-WP04, F1-WP06 | A run launched from the API completes, and metrics are stored for all 3 scales |
| P2-WP07 | **Backtest UI:** list, form, detail (metrics panel, equity/drawdown, trade markers, sensitivity table + 1.5× warning) | 4 | M | P2-WP06, F3-WP06 | Full flow from the browser; warning banner shows on a deliberately cost-fragile config |
| P2-WP08 | **`signals` app + dispatcher + inference v0:** models, `bars.persisted` event from ingestor, `bar_close_dispatcher`, `run_inference` with policy v0 (cooldown, session, spread sanity, empirical EV), pipeline events, `signals:*` stream, Ninja routes `GET /signals`, `GET /signals/{id}` | 4 | M | P2-WP02, P2-WP06 | Signals appear within 2 s of bar close on watched symbols, and each has a `feature_hash` and reason codes |
| P2-WP09 | **`paper` tracker:** command, bid/ask resolution, R/slippage/MAE/MFE/swap, restart catch-up, stats endpoint incl. live-vs-backtest expectancy, optional manual-fill linking | 4 | M | P2-WP08, F2-WP09 | Replay test on recorded ticks resolves fixture signals exactly as hand-computed, and a restart mid-trade resolves correctly |
| P2-WP10 | **Live signal feed UI:** SignalCard (countdown, live R, resolve animation), feed page + symbol side panel, toasts, Notification API, sound, filters, `BarrierBox` primitive | 4 | M | P2-WP08, P2-WP09 | A new signal toasts, appears on the chart as a box, counts down and animates on resolution |
| P2-WP11 | **Pipeline animation v1:** `pipeline` WS channel, PipelineGraph with Motion packet travel, node inspector drawer, greyed P3 nodes | 4 | M | P2-WP08, F3-WP07 | Each bar close animates, and clicking "Costs/EV" shows the EV arithmetic for the last decision |
| P2-WP12 | **Indicator panes:** `/bars/{name}/indicators` endpoint + RSI/MACD/ADX panes | 2 | M | P2-WP01, P1-WP08 | Panes align with candles and update on bar close |
| P2-WP13 | **Backtest replay scrubber:** synced candles/trades/equity animation on the detail page | 2 | S | P2-WP07 | Scrubbing moves all three views in sync |
| P2-WP14 | **Baseline report:** all rules × watched symbols on **H1 and M15**, 1/1.5/2× costs, output `docs/reports/p2-baseline.md` + feed `p_tp_empirical` table | 2 | M | P2-WP06 | Report published, and policy v0 reads empirical hit rates from it |

**Phase-specific total:** 47 h

### Phase budget (everything scheduled in P2)

| Source | WPs | Hours |
|---|---|---|
| P2 | WP01–WP14 | 47 |
| X1 (Ask Claude v1) | WP01–WP07 | 25 |
| X2 | WP06–WP07 | 7 |
| F2 | WP09 | 2 |
| F1 | WP10 | 1.5 |
| **Total** | | **82.5 h ≈ 7–8 weeks** |

> **Budget note:** this is above the master's 4–5 weeks. Ask Claude v1 alone is ~25 h.
>
> To hit the master range, defer the S items (P2-WP05, P2-WP13, F1-WP10 ≈ 6.5 h) and consider shipping X1 v1 *after* the paper tracker is live (Recommendation 3 puts the tracker first).

## 6. Testing (see [X2](X2-testing-quality-governance.md))

- Unit: indicator parity, rule fixtures, cost model, simulator, metrics, EV math.
- **Parity test:** the same fixture signal resolved by `barrier_sim` (bar data) and `paper_tracker` (tick data built from the same bars) gives the same outcome when no intrabar ambiguity exists.
- Integration (X2-WP06): fake gateway → ingest → dispatcher → inference → WS `signal` received.
- Playwright (X2-WP07): signal appears in feed → resolves.

## 7. Exit criteria

**Master:** *"Paper tracker resolving signals; baseline reports after costs; Ask Claude working end-to-end within budget."*

Measurable checks:

- [ ] Paper tracker has resolved ≥ 30 live signals across ≥ 3 symbols, with outcomes reconciled by hand for 5 of them (bid/ask correct).
- [ ] `docs/reports/p2-baseline.md` exists with metrics at 1×/1.5×/2× costs for every rule × symbol × {H1, M15}, and states plainly which (if any) baselines survive 1.5×.
- [ ] Implementation shortfall view shows live vs backtest expectancy per strategy.
- [ ] Ask Claude v1 exit checks met ([X1 §7](X1-ask-claude-advisor.md#7-exit-criteria)): an end-to-end ask in each v1 mode, with spend under the configured daily cap.
- [ ] Master deliverables present: backtest page, metrics panel, cost sensitivity, Ask Claude drawer and result card.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Race between ingest commit and inference | Dispatcher consumes `bars.persisted` emitted **after** commit |
| Backtest/live mismatch | One resolution rule set shared by the simulator and the tracker, plus the parity test |
| Overfitting rule parameters via sweeps | Treat sweeps as exploration. Report defaults plus the walk-forward-chosen params only, and count trials (feeds deflated Sharpe in P3) |
| Notification fatigue | Per-symbol/strategy filters, quiet hours in Settings |

## 9. Open questions / verify at build time

- TA-Lib 0.6.x wheel availability for the backend container's Python (expected since 0.6.5).
- vectorbt 0.26.x compatibility with current numpy/pandas.
- Default timeframes for live signals. The suggestion is **H1 primary, M15 secondary** (Recommendation 5).
