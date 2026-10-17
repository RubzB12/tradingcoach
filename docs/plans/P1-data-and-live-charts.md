# P1 — Data + Live Charts

> **Type:** Phase · **Master effort:** 3–4 wks · **This plan:** 27 h own + 73 h foundation/testing = **100 h** (see §5 budget note)
> **Master plan refs:** Roadmap Phase 1; §1 real-time pattern; §2 Architecture + Storage; §5 Lightweight Charts / "keep tick updates out of React state"; data-quality caveats
> **Index:** [README](README.md)

## 1. Goal and context

This phase builds the live data path end to end: **gateway → Redis Streams → TimescaleDB/Parquet → Django (REST + Channels) → Next.js live multi-pane chart**, plus history back-fill, symbol search, and a health banner.

It is also the phase where the three foundation plans are built. Everything after it depends on this phase being solid.

## 2. Scope

**In:**
- [F1](F1-backend-platform-django.md) WP01–WP09
- [F2](F2-mt5-gateway.md) WP01–WP08
- [F3](F3-frontend-platform-nextjs.md) WP01–WP08
- [X2](X2-testing-quality-governance.md) WP01–WP05
- The phase-specific WPs below

**Out:** indicators, signals and backtests (P2); per-indicator panes beyond a placeholder (P2).

## 3. Dependencies

- [P0](P0-spike-mt5-connectivity.md) exit criteria met.
- Recordings available for fake MT5.

## 4. Design

### 4.1 `marketdata` app — data model

| Model / table | Key fields | Notes |
|---|---|---|
| `Symbol` | `name` (canonical, unique), `broker_name`, `asset_class` (fx\|stock_cfd\|index_cfd\|commodity\|crypto), `digits`, `point`, `contract_size`, `volume_min`, `volume_step`, `currency_base/profit/margin`, `is_watched`, `group` (for model grouping, P3) | Upserted from `symbols.snapshot` |
| `SymbolSnapshot` | `symbol` FK, `ts`, `spread`, `swap_long`, `swap_short`, `swap_rollover3days`, `trade_mode`, `sessions` (JSON) | Keeps swap/session history for cost models |
| `bar` (hypertable) | PK (`symbol`, `tf`, `time`); `open/high/low/close` (`numeric(18,8)`), `tick_volume`, `spread`, `real_volume`, `source` (mt5\|agg) | Stores `M1`, `H4`, `D1` from MT5. Chunk interval 7 days. Compression after 30 days |
| `tick` (hypertable) | PK (`symbol`, `time_msc`, `seq`); `bid`, `ask`, `last`, `volume`, `flags` | **Watched symbols only.** Retention 30 days (configurable). Compression after 3 days |
| `bar_m5`, `bar_m15`, `bar_h1` | Continuous aggregates over `bar WHERE tf='M1'` | UTC-aligned buckets are correct for whole-hour broker offsets. H4/D1 come from MT5 because they align to broker midnight |
| `IngestCheckpoint` | `stream`, `last_id`, `updated_at` | For restart safety, in addition to consumer groups |

A unified read view `bars_all(symbol, tf, time, …)` UNIONs the MT5-stored and aggregate TFs, so the API has one query path.

### 4.2 Processes

```
[sd_gateway] ──XADD──► ticks:*, bars:*:*, symbols.snapshot, gateway.health
     ▲                       │
     │ gateway.requests      ├─► ingest_streams  (consumer group "ingestor")  ─COPY─► bar, tick, Symbol*
     │                       └─► stream_fanout   (consumer group "fanout")   ─group_send─► Channels groups
backfill_history (cmd) ──► gateway.requests ─► gateway.responses:{id} ─► COPY into bar
lake_export (Celery, nightly 02:00 UTC) ─► data/lake/bars/symbol=…/tf=…/date=…/part.parquet
```

- **`ingest_streams`:** `XREADGROUP` over `ticks:{s}` and `bars:{s}:{tf}` for watched symbols. The key list refreshes every 30 s from `Symbol.is_watched` and also writes `gateway:watchlist`. Batches 500 rows or 250 ms, writes with `copy_rows` upsert, `XACK`s after commit. Non-final bars are skipped; only `final=true` bars are persisted.
- **`stream_fanout`:** a separate consumer group, so that UI fan-out never waits on DB writes.
  - **Coalesces ticks** to the latest per symbol every 100 ms.
  - Forwards forming and final bars.
  - Assigns `seq` per key.
  - Calls `channel_layer.group_send(f"sym.{s}.tick", …)`.
  - Health messages go to group `health`.
- **Latency instrumentation:** each envelope carries `src_ts` (MT5 `time_msc`) and `gw_ts` (gateway XADD time). The client computes `render_ts − src_ts` and reports p50/p95 to `POST /api/v1/telemetry/latency`, which is sampled 1 in 20.

### 4.3 API (Ninja, `/api/v1`)

| Method & path | Purpose |
|---|---|
| `GET /symbols?q=&group=&watched=` | Search the catalog. `q` matches name/description |
| `GET /symbols/{name}` | Detail + latest snapshot (spread, swaps, sessions, trade_mode) |
| `PUT /symbols/{name}/watch` `{watched: bool}` | Toggle the watchlist. Triggers gateway subscribe and a back-fill job |
| `GET /bars/{name}?tf=M1&before=&limit=1000` | Cursor-paged history, newest-first window returned ascending |
| `GET /bars/{name}/gaps?tf=M1&from=&to=` | Gap report (used by exit check and UI caveats) |
| `POST /telemetry/latency` | Client latency samples |

### 4.4 Frontend

- **`/` (overview):** a watchlist table with last price, spread and change %, live-updating from tick subscriptions.
- **`/symbols/[symbol]`:**
  - header: name, asset class, session status, live bid/ask/spread
  - TF switcher: M1/M5/M15/H1/H4/D1
  - `<PriceChart>` with pane 1 candles, pane 2 volume (tick volume, labelled), pane 3 spread
  - an indicator pane placeholder for P2
  - history loaded via TanStack Query; live forming bar via the `bar` channel; resync on seq gap
- **Data-quality caveats** popover: "tick volume ≠ real volume", "spread column is per-bar min/typical", weekend gaps, broker-specific feed.

## 5. Work packages (phase-specific)

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| P1-WP01 | **marketdata models + migrations:** Symbol, SymbolSnapshot, `bar`/`tick` hypertables, compression/retention policies, `bar_m5/m15/h1` continuous aggregates + refresh policies, `bars_all` view, admin | 3 | M | F1-WP07 | Migrations apply on a fresh DB, and continuous aggregates refresh with correct OHLC on fixture data |
| P1-WP02 | **`ingest_streams` command:** consumer group, dynamic watched-key list, batching, COPY upsert, ack-after-commit, checkpoint, graceful shutdown, compose service | 3 | M | P1-WP01, F2-WP02 | Killing and restarting the ingestor loses no bars and creates no duplicates (count check vs stream) |
| P1-WP03 | **History back-fill:** `backfill_history --symbol --tf --since` command + Celery task triggered on watch toggle; uses gateway history service; gap detector (`/gaps`) and auto-repair for watched symbols nightly | 3 | M | P1-WP02, F2-WP04 | Watching a new symbol back-fills its full available M1/H4/D1 history, and the gap report is empty for market hours |
| P1-WP04 | **Parquet lake export:** nightly Celery task writing partitioned Parquet via Polars from Timescale (COPY TO / psycopg), `sd_core.lake.read(symbol, tf, start, end)` DuckDB helper for research | 2 | S | P1-WP01, F1-WP06 | `research/` notebook loads 1 year of EURUSD M1 from the lake in < 3 s |
| P1-WP05 | **Ninja routes:** symbols search/detail/watch, bars history with cursor paging, gaps, telemetry; schemas in `sd_contracts` where shared | 2.5 | M | P1-WP01, F1-WP05 | OpenAPI documents all routes; 1,000 M1 bars return in < 150 ms locally |
| P1-WP06 | **`stream_fanout` + consumer wiring:** fan-out command, tick coalescing, per-key `seq`, health forwarding, DashboardConsumer subscribe → group add/discard with symbol validation | 3 | M | F1-WP04, F2-WP02 | Two browser tabs subscribed to different symbols receive only their own streams, and seq numbers are contiguous |
| P1-WP07 | **Symbol picker + watchlist:** overview table (live), cmdk search wired to `/symbols`, watch toggle, group filter | 2.5 | M | F3-WP03, F3-WP07, P1-WP05 | You can find, watch, and see a live price for a new symbol in < 30 s |
| P1-WP08 | **Symbol page live chart:** TF switcher, history load + live merge, volume and spread panes, indicator-pane placeholder, session status, live bid/ask | 3.5 | M | F3-WP06, P1-WP06 | Candles update live and stay continuous across a TF switch, and a WS reconnect causes no visual gap after resync |
| P1-WP09 | **Health banner + latency telemetry:** wire `health` channel, stale detection (no tick > 10 s in session), latency sampling + `/telemetry/latency`, small latency readout in Settings | 2 | M | F3-WP07, P1-WP06 | Stopping the gateway shows the banner in ≤ 10 s, and latency p50/p95 are visible |
| P1-WP10 | **Data-quality caveats UI:** popover + per-symbol flags (FX tick volume, weekend gap markers on chart) | 1 | S | P1-WP08 | Caveats are visible on every symbol page |
| P1-WP11 | **Exit verification:** `scripts/latency_report.py` (from telemetry table), `scripts/gap_report.py` over 5 trading days; `docs/reports/p1-exit.md` | 1.5 | M | all | Report shows both exit metrics with pass/fail |

**Phase-specific total:** 27 h

### Phase budget (everything scheduled in P1)

| Source | WPs | Hours |
|---|---|---|
| F1 | WP01–WP09 | 24 |
| F2 | WP01–WP08 | 18 |
| F3 | WP01–WP08 | 20 |
| X2 | WP01–WP05 | 11 |
| P1 | WP01–WP11 | 27 |
| **Total** | | **100 h ≈ 8–10 weeks at 10–12 h/wk** |

> **Budget note:** the master plan estimates 3–4 weeks for Phase 1, but this phase also carries all of the platform set-up. Bottom-up, it comes to ~100 h.
>
> The **"S" (should)** items total ~12 h and can slip to P2 if you want an earlier working chart: F2-WP07, F3-WP07/WP08, P1-WP04, P1-WP10, X2-WP04/WP05.
>
> Claude Code doing much of the implementation should shorten this considerably. Re-estimate after F1.

## 6. Testing (see [X2](X2-testing-quality-governance.md))

- `ingest_streams`: idempotency (replay the same stream twice → same row counts) and crash-recovery tests using the fake gateway.
- Continuous aggregate correctness against Polars-resampled M1 fixtures.
- Consumer tests: subscribe isolation, invalid symbol rejection, seq contiguity.
- Playwright: login → watch symbol → live candle updates (offline profile).

## 7. Exit criteria

**Master:** *"Live chart latency <300 ms; gap-free M1 for watched symbols."*

Measurable checks:

- [ ] End-to-end latency (MT5 `time_msc` → chart `series.update`) **p95 < 300 ms** over ≥ 1 trading day of telemetry samples for ≥ 3 watched symbols.
- [ ] **Zero M1 gaps** during each watched symbol's trading sessions over 5 consecutive trading days in `bar`, as verified by `gap_report.py` against the broker's own `copy_rates_range`.
- [ ] Ingest restart and gateway reconnect each cause no data loss (tested once each, documented in `p1-exit.md`).
- [ ] Master deliverables present: monorepo, compose, typed WS contract, history back-fill, symbol search (`symbols_get` groups).

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| DB write latency slows the UI | Fan-out runs in a separate consumer group from ingest, so the UI never waits on DB writes |
| Tick table growth | Store ticks only for watched symbols, with retention + compression. Bars are the long-term store |
| Continuous aggregate misalignment for H4/D1 | Store H4/D1 straight from MT5 (by design). Add a test comparing the H1 aggregate against MT5 H1 for a sample |
| WS fan-out CPU at high tick rates | 100 ms coalescing. msgpack framing if needed |

## 9. Open questions / verify at build time

- Tick retention length (default 30 days). Increase it if you plan tick-level backtests in P4 (NautilusTrader).
- Whether to also persist forming-bar snapshots. Default is no.
