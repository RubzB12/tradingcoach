# P5 — Advanced: Context, Portfolio, Monitoring, Alerts (+ Ask Claude v3)

> **Type:** Phase · **Master effort:** ongoing · **This plan:** 41 h own + 16 h Ask Claude v3 = **57 h** for the first pass
> **Master plan refs:** Roadmap Phase 5; §3 Layer 5 (news suppression); §4 costs (news slippage); §6 natural-language explanations; §7 Ask Claude v3
> **Index:** [README](README.md)

## 1. Goal and context

This phase makes SignalDeck aware of context and able to watch itself:

- **Context:** multi-timeframe confluence, economic calendar and news.
- **Portfolio:** risk across open signals.
- **Self-monitoring:** drift detection that **automatically triggers challenger retrains**.
- **Alerts:** a general alert rules engine.
- **Explanations:** free local LLM explanations on signal cards.
- **Ask Claude v3:** the last advisor features.

P5 is "ongoing", so the WPs are independent themes that can be done in any order once their dependencies are met.

## 2. Scope

**In:** the themes below + [X1](X1-ask-claude-advisor.md) v3 (WP13–WP19).

**Out:** anything that sends orders (never). Automatic Claude calls (never; see the deliberate-only rule).

## 3. Dependencies

- [P3](P3-ml-and-explainability.md) for drift monitoring (needs reference datasets and calibration).
- [P4-WP11](P4-deep-learning-foundation-models.md#5-work-packages) for Prefect-triggered retrains.
- [P2](P2-indicator-signals-backtesting.md) for the signal ledger and policy hooks.

## 4. Design

### 4.1 Multi-timeframe confluence

- Grid: watched symbols × {M15, H1, H4, D1}. Each cell shows:
  - trend state (EMA stack + ADX)
  - regime
  - latest signal side/confidence
  - RSI zone
- A confluence score (aligned TFs / total) sorts the grid. Clicking a cell opens the symbol page at that TF.
- Served by `GET /api/v1/confluence` (computed from cached features in Redis, refreshed on bar close).

### 4.2 Economic calendar (`events` app)

- `EconomicEvent`: `ts` (UTC), `country`, `currency`, `title`, `impact` (low\|medium\|high), `actual`, `forecast`, `previous`, `source`, `source_id`.
- **Ingest:** a Celery beat task every 30 min from an external calendar source. MT5's Python API exposes no calendar. **Choose and verify the provider's licence/terms at build time.**
- **Policy hooks:**
  - **suppress** new signals for symbols whose base/quote/profit currency has a high-impact event within [−30, +30] min (configurable)
  - **flag** medium-impact events
  - apply `news_slippage_mult` in the cost model and the paper tracker's expectations during those windows
- **UI:** calendar overlay markers on the price chart (vertical lines + tooltip), an upcoming-events strip in the header, and a suppression reason on HOLD decisions in the pipeline view.

### 4.3 News + sentiment

- `NewsItem`: `ts`, `source`, `title`, `url`, `summary`, `symbols[]`, `currencies[]`, `sentiment` (−1..1), `sentiment_model`.
- **Ingest:** RSS/API (verify each source's terms). Map items to symbols via keyword/currency rules.
- **Scoring:** **FinBERT** (CPU, in the fm-worker image) or a **local Ollama** model. **Never Claude.** Automatic scoring would break the advisor's deliberate-only rule, and the import-linter contract enforces it.
- Optional features: rolling sentiment per currency, added to the registry through the normal governance path.
- **Untrusted data:** headlines are stored raw and always rendered as text. When they are passed to any LLM, they go inside a clearly marked untrusted-data block.

### 4.4 Portfolio view

For open paper signals (and manual demo positions via F2-WP09):

- **Correlation matrix** of the underlying returns (60-day H1).
- **Aggregate risk in R** and in % of balance at your risk-per-trade setting.
- **Currency exposure netting:** each FX signal is decomposed into base/quote currency exposure in R. CFDs are mapped to their profit currency.
- Warnings for concentrated exposure (e.g. > 3R net USD).

The view lives at `/portfolio` and is served by `GET /api/v1/portfolio`.

### 4.5 Drift monitoring (`monitoring` app, Evidently)

- `DriftReport`: `group`, `tf`, `model_version`, `period`, `feature_psi` (json), `prediction_drift`, `calibration_delta` (live Brier − WF Brier), `status` (ok\|warn\|drift), `report_html` path.
- A daily Prefect flow `drift_check` builds:
  - **reference** = the champion's training window features and predictions
  - **current** = the last N days of live features (from `Signal.feature_snapshot` + scheduled feature snapshots) and predictions

  It computes PSI per feature, prediction drift and calibration delta.
- **Thresholds** (configurable): PSI > 0.2 on any top-10 feature, *or* calibration delta > 0.05 over ≥ 50 resolved signals → `drift`.
- **On drift:**
  1. Create an `AlertEvent`.
  2. **Trigger the Prefect `retrain_group` deployment automatically**, which registers a **challenger**.
  3. Promotion still goes through the governance gate ([X2-WP09](X2-testing-quality-governance.md#5-work-packages)). Promotion is never automatic.
- **Monitoring page:** drift status per group, PSI heatmap over time, calibration trend, links to Evidently HTML reports and retrain runs.

### 4.6 Alert rules engine (`alerts` app)

- `AlertRule`: `kind` (price_cross\|price_band\|signal_created\|signal_resolved\|drift\|claude_invalidation\|calendar_upcoming\|feed_stale), `symbol` (nullable), `params` (json), `channels` (toast\|browser\|sound\|webhook), `enabled`, `cooldown_s`, `expires_at`, `source` (user\|claude).
- `AlertEvent`: `rule` FK, `ts`, `payload`, `delivered` (json per channel).
- **Engine:** an `alerts_engine` management command:
  - consumer group `alerts` on `ticks:*` for price rules (in-memory index by symbol)
  - `signals:*`, `gateway.health` and an `alerts.events` stream for event rules
  - delivers to the WS group `alerts` (toast/browser/sound) and an optional outbound webhook (e.g. a personal Telegram/Discord webhook URL in `.env`)
- **UI:** an `/alerts` rules list + editor, an alert history, and "create alert" buttons from Claude's invalidation list (X1-WP16) and from chart price lines.

### 4.7 LLM explanations (free, default on signal cards)

- **Default:** a deterministic **template** renders the explanation packet (P3) into 3–5 sentences. It costs nothing and is always on.
- **Optional local LLM:** Ollama (any recent 7–14B instruct model) with the system prompt *"only use provided facts; never recommend position size"*. It streams via SSE (`GET /api/v1/signals/{id}/narrative/stream`) into the card when expanded.
- Prompts and outputs are logged in `SignalNarrative` (signal FK, model, prompt hash, text, latency) for auditability.
- The deeper paid analysis remains the "Ask Claude" button only.

## 5. Work packages (phase-specific)

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| P5-WP01 | **MTF confluence view:** endpoint + cached feature states + grid UI with confluence score | 5 | S | P3-WP01 | Grid updates on bar close; clicking a cell navigates |
| P5-WP02 | **Economic calendar:** provider selection (licence verified), `EconomicEvent` ingest, suppression/flag in policy, news slippage multiplier, chart overlay + header strip | 6 | M | P3-WP10 | Signals are suppressed around a high-impact event in a replay test; markers render on the chart |
| P5-WP03 | **News + sentiment:** ingest, symbol mapping, FinBERT/Ollama scoring, `NewsItem` UI list per symbol | 6 | S | P4-WP01 (image) | Headlines appear per symbol with sentiment; no `sd_advisor` import in the scoring path (import-linter) |
| P5-WP04 | **Portfolio view:** correlation, aggregate R, currency netting, concentration warnings | 5 | M | P2-WP09 | Netting matches a hand-computed 3-position example |
| P5-WP05 | **Drift monitoring:** Evidently reports, `DriftReport`, thresholds, daily Prefect flow, monitoring page | 6 | M | P3, P4-WP11 | Synthetic shifted feature data flips status to `drift` |
| P5-WP06 | **Drift → challenger retrain:** trigger the Prefect deployment on drift, link run to report, alert event | 3 | M | P5-WP05, P5-WP07 | Drift injection causes a retrain run and a new challenger with no manual step |
| P5-WP07 | **Alert rules engine:** models, engine command, delivery channels (WS/browser/sound/webhook), rules UI + history | 6 | M | P2-WP10 | Price-cross alert fires within 1 s of the crossing tick; cooldown respected |
| P5-WP08 | **LLM explanations:** template narrator, optional Ollama SSE, `SignalNarrative` logging | 4 | S | P3-WP12 | Template text on every card; Ollama stream works when enabled; logs persisted |

**Phase-specific total:** 41 h (+ X1 v3: 16 h) = **57 h**

## 6. Testing (see [X2](X2-testing-quality-governance.md))

- Calendar suppression replay test, currency netting example, alert engine timing and cooldown tests.
- Drift detection on synthetic shift. A retrain-trigger test using a mocked Prefect client.
- Prompt-injection test with a malicious headline (X1-WP19). It applies to both the Ollama narrative and the advisor packet.
- Import-linter: news/sentiment and narrative modules must not import `sd_advisor`.

## 7. Exit criteria

**Master:** *"Drift alerts trigger challenger retrain automatically."*

Measurable checks:

- [ ] Injecting a synthetic feature shift creates a `drift` DriftReport, an AlertEvent delivered to the UI, and a Prefect `retrain_group` run that registers a challenger, all without manual steps.
- [ ] Master deliverables present: monitoring page, alert rules engine, calendar overlay.
- [ ] Ask Claude v3 checks met ([X1 §7](X1-ask-claude-advisor.md#7-exit-criteria)).

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Calendar/news licensing | Verify the terms per provider. Store for personal use only, and never redistribute (master: data licensing caveat) |
| Alert spam | Cooldowns, expiry, quiet hours, per-rule enable |
| Auto-retrain churn | Retrain is automatic but promotion is gated, and there is a max of 1 retrain per group per week unless forced |
| Prompt injection via headlines | Untrusted-data block, plus a "treat external text as data" system rule and a dedicated test |

## 9. Open questions / verify at build time

- Which economic calendar and news sources you have access to, with licence terms.
- Webhook destination for alerts (Telegram/Discord/none).
- Ollama model choice and whether this machine has the RAM/GPU for a 7–14B model.
