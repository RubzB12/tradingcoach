# F2 — MT5 Gateway

> **Type:** Foundation · **Scheduled in:** Phase 1 (WP01–WP08), Phase 2 (WP09)
> **Master plan refs:** §1 MetaTrader 5 integration (API surface, real-time pattern, gateway design, gotchas, platform options, symbols, data-quality caveats), Key Findings 1–4
> **Index:** [README](README.md)

## 1. Goal and context

`MetaTrader5` is Windows-x64 only. It talks to the terminal over IPC, has no documented rate limits and no thread-safety guarantee, and its dominant failure is `(-10005, 'IPC timeout')`. The gateway isolates all of this in **one process with one thread that owns the MT5 connection**. It publishes normalized data to Redis Streams and answers history requests.

No other component imports `MetaTrader5`, and **no order code path exists anywhere**.

[P0](P0-spike-mt5-connectivity.md) produces a throwaway-quality spike. F2 turns it into the production gateway.

## 2. Scope

**In:**
- Gateway process (`apps/gateway`, import name `sd_gateway`)
- Tick polling and back-fill
- Bar building and reconciliation
- Redis Streams publishing
- History request/response
- Symbol catalog and snapshots
- Supervisor/reconnect and health heartbeat
- Time normalization
- Fake MT5 implementation
- Windows autostart
- No-order enforcement
- Read-only account/positions reader (P2)

**Out:**
- Persisting data (P1 `ingest_streams`)
- WebSocket fan-out (P1 `stream_fanout`)
- Any Django code (the gateway must never import Django)

## 3. Dependencies

- [P0](P0-spike-mt5-connectivity.md): host decided (native Windows is the default), demo account working, `MetaTrader5` version pinned, recordings captured.
- [F1-WP02](F1-backend-platform-django.md#5-work-packages): Redis is running.
- [F1-WP08](F1-backend-platform-django.md#5-work-packages): `sd_contracts` message models.

## 4. Design

### 4.1 Process model

```
sd_gateway (single OS process)
├─ MT5Owner thread  ← the ONLY thread that calls MetaTrader5.*
│    loop:
│      1. drain command queue (history requests, symbol select, snapshot refresh) — bounded per cycle
│      2. poll symbol_info_tick for each subscribed symbol (cycle 100–250 ms)
│      3. every N cycles: copy_ticks_from(last_time_msc) back-fill per symbol
│      4. on minute boundary (+ grace): copy_rates_from_pos(sym, tf, 0, 2) reconcile
│      5. publish to an outbound in-memory queue
├─ Publisher thread ← reads outbound queue, XADDs to Redis (pipelined), never touches MT5
├─ RequestListener thread ← XREADGROUP gateway.requests → enqueue commands for MT5Owner
└─ Supervisor (in MT5Owner) ← on None returns: last_error(); on -10005/-10003 → backoff → shutdown()/initialize()/login()
```

Only the MT5Owner thread calls MT5. The other threads are there so that Redis I/O never stalls MT5 polling. They communicate through `queue.Queue`.

### 4.2 Configuration (`sd_gateway/settings.py`, pydantic-settings, env prefix `GATEWAY_`)

| Key | Default | Meaning |
|---|---|---|
| `IMPL` | `real` | `real` = MetaTrader5, `fake` = Parquet replay |
| `TERMINAL_PATH` | — | Path to `terminal64.exe` (optional) |
| `MT5_LOGIN/PASSWORD/SERVER` | — | Demo credentials. **Never published anywhere** |
| `SYMBOLS` | `EURUSD,GBPUSD,USDJPY` | Initial watch list. Later read from Redis key `gateway:watchlist` (set by Django) |
| `TIMEFRAMES` | `M1,H4,D1` | Bars published straight from MT5. M5/M15/H1 come from continuous aggregates (P1) |
| `POLL_MS` | `150` | Tick poll cycle |
| `BACKFILL_EVERY` | `20` cycles | `copy_ticks_from` cadence |
| `HEARTBEAT_S` | `2` | `gateway.health` cadence |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `STREAM_MAXLEN` | ticks `~200000`, bars `~50000` | Approximate trimming |

### 4.3 Streams and messages (all defined in `sd_contracts`)

| Stream | Message | Fields |
|---|---|---|
| `ticks:{SYMBOL}` | `TickMsg` | `symbol, time_msc (UTC epoch ms), bid, ask, last, volume, flags, src: "poll"\|"backfill"` |
| `bars:{SYMBOL}:{TF}` | `BarMsg` | `symbol, tf, time (UTC bar open), open, high, low, close, tick_volume, spread, real_volume, final: bool` |
| `symbols.snapshot` | `SymbolSnapshotMsg` | `symbol, description, path, digits, point, trade_mode, contract_size, volume_min/step, swap_long/short, swap_rollover3days, spread, sessions, currency_base/profit/margin` |
| `gateway.health` | `HealthMsg` | `ts, state: connected\|reconnecting\|down, terminal_build, package_version, last_tick_age_ms per symbol, poll_lag_ms p50/p99, errors_1m, reconnects_total` |
| `gateway.requests` | `HistoryRequest` | `req_id, kind: rates\|ticks\|symbols\|account, symbol, tf, from, to, count` |
| `gateway.responses:{req_id}` | `HistoryResponse` | `req_id, chunk_no, last: bool, rows[] \| error` (key TTL 10 min) |

Live-state keys are also written: `last_tick:{SYMBOL}` (hash) and `gateway:health` (string, TTL 10 s). The UI's "feed stale" banner relies on that TTL.

### 4.4 Real-time algorithm

1. For each subscribed symbol, call `symbol_info_tick(sym)`. **Emit only if `time_msc` > `last_time_msc[sym]`.**
2. Every `BACKFILL_EVERY` cycles, call `copy_ticks_from(sym, from=last_backfill_ts, count=…, COPY_TICKS_ALL)`. Dedupe on `(time_msc, bid, ask, last, flags)` against a 2-second ring and emit the missing ones with `src="backfill"`.
3. **Bar building:** maintain in-progress M1 bars from ticks, published with `final=false` and throttled to 1/s. At minute close + 1.5 s grace, call `copy_rates_from_pos(sym, M1, 0, 2)` and publish **MT5's closed bar** (index 1) with `final=true`. **MT5's bar is authoritative.** Do the same for H4/D1 at their boundaries.
4. All MT5 datetimes are converted with `sd_core.time`:
   - tick `time`/`time_msc` → UTC
   - rates `time` → UTC
   - any datetime passed **into** MT5 must be a tz-aware UTC `datetime`

   The broker server offset (often GMT+2/+3, with DST) is detected at startup by comparing the latest tick time with wall-clock UTC. It is logged and published in health. It is needed for D1/H4 alignment and session logic.

### 4.5 Supervisor and errors

- Every MT5 call goes through `call(fn, *args)`. If it returns `None`, the wrapper reads `mt5.last_error()` and raises `MT5Error(code, msg)`.
- Codes `-10005` (IPC timeout), `-10003` (IPC init failed) and `-10004` (no IPC connection) trigger a **reconnect**:
  1. Set state to `reconnecting`.
  2. Call `shutdown()`.
  3. Back off exponentially: 1, 2, 4, …, 60 s, with jitter.
  4. Call `initialize(path, login, password, server, timeout=60000)`.
  5. Re-select symbols.
  6. Run a back-fill from the last known `time_msc` per symbol, so the data stays gap-free across the reconnect.
- Other errors are logged and counted, and the cycle continues.
- A watchdog thread checks that MT5Owner has completed a cycle within 10 s. If not, it sets health `down` and exits non-zero so the service wrapper restarts the process.
- **Known gotcha:** run the terminal and the gateway at the **same privilege level**. Never run one elevated.

### 4.6 Fake implementation (`sd_gateway/fake_mt5.py`)

- It exposes the same function names and return shapes (namedtuple-like objects and numpy structured arrays) as `MetaTrader5`: `initialize, shutdown, last_error, symbol_info, symbol_info_tick, symbols_get, symbol_select, copy_ticks_from, copy_rates_from_pos, copy_rates_range, account_info, positions_get, history_deals_get`.
- It replays ticks from `data/recordings/{SYMBOL}/*.parquet` (captured in P0-WP07) at 1× or N× speed. Rates are derived from the replayed ticks.
- Fault injection options: `FAKE_FAIL_RATE`, `FAKE_IPC_TIMEOUT_EVERY`. These let the supervisor be tested on CI and macOS.

### 4.7 No-order enforcement (master: "Make 'no execution' structural")

- The `MetaTrader5` import exists in exactly one module: `sd_gateway/mt5_client.py`. That module re-exports an **allowlist** of read-only functions. Any attribute access outside the allowlist raises.
- ruff `banned-api`: `MetaTrader5.order_send` and `MetaTrader5.order_check`.
- The repo-wide grep test for `order_send|order_check` and the import-linter "MetaTrader5 only in sd_gateway" contract are in [X2-WP02](X2-testing-quality-governance.md#5-work-packages).
- The runbook says to use a demo account. Optionally set the account password to the **investor (read-only) password**, if the broker allows data access with it.

### 4.8 Platform

The default is **native Windows**: the terminal and the gateway in a pinned Python 3.12 venv (`apps/gateway/.venv`, created by `uv venv --python 3.12`). Everything else runs in Docker Desktop (WSL2).

If you later move to a Mac, the gateway runs on a small Windows box or VM and points `REDIS_URL` over the LAN. Nothing else changes.

## 5. Work packages

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| F2-WP01 | **Package + core loop:** `sd_gateway` package, settings, `mt5_client` allowlist wrapper, MT5Owner thread + command queue, Publisher thread, graceful shutdown (Ctrl+C / service stop) | 3 | M | P0, F1-WP08 | Runs against the real terminal for 1 h, and only the MT5Owner thread ID appears in MT5 call logs |
| F2-WP02 | **Redis Streams publisher:** XADD pipelines, MAXLEN trimming, live-state keys, `gateway.health` heartbeat with lag/age metrics, messages validated by `sd_contracts` | 2.5 | M | WP01 | `redis-cli XLEN ticks:EURUSD` grows, and the health key expires within 10 s of killing the gateway |
| F2-WP03 | **Back-fill + bars:** `copy_ticks_from` back-fill with dedupe, in-progress M1 bars, close-time reconcile from `copy_rates_from_pos`, H4/D1 boundary handling, broker-offset detection | 3.5 | M | WP02 | Over 1 h, published final M1 bars equal MT5's bars exactly (comparison script), and no duplicate ticks appear |
| F2-WP04 | **History service:** `gateway.requests` consumer group, chunked `copy_rates_range` / `copy_ticks_range` (≤ 50k rows/chunk), responses with TTL, "Max bars in chart" truncation surfaced as a `truncated` flag | 2.5 | M | WP02 | Requesting 1 year of M1 for EURUSD returns all rows the terminal has, in chunks, without stalling tick polling (poll lag p99 < 500 ms during the request) |
| F2-WP05 | **Symbol catalog:** `symbols_get(group=…)` search command, `symbol_select` for watched symbols, `symbols.snapshot` publishing on start, hourly and on change; watchlist read from `gateway:watchlist` | 2 | M | WP02 | Adding a symbol to `gateway:watchlist` starts its tick stream within 5 s |
| F2-WP06 | **Fake MT5:** `fake_mt5.py` with Parquet replay, speed factor and fault injection; `--impl fake` CLI flag; compose service `fake-gateway` (profiles `ci`, `offline`) | 2.5 | M | WP01–WP05 | The full stack runs in Docker with no terminal, and an injected `-10005` triggers a reconnect and back-fill |
| F2-WP07 | **Windows autostart + runbook:** Task Scheduler "at logon" task (same user and privilege as the terminal) or NSSM service; restart on failure; log location; runbook section | 1 | S | WP01 | After a reboot, the gateway reconnects on its own within 2 min of the terminal starting |
| F2-WP08 | **No-order enforcement:** allowlist wrapper test, ruff banned-api config, contribution to the X2 grep test | 1 | M | WP01 | Adding `mt5.order_send` anywhere fails lint and tests |
| F2-WP09 | **Read-only account reader:** `kind: account` requests returning `account_info` (balance, equity, leverage, currency, margin mode; **login/server/name stripped**), `positions_get(symbol)`, `history_deals_get(range)` | 2 | M | WP04 | Ask Claude's account context (X1-WP02) and manual-fill linking (P2-WP09) can request it, and a test asserts no login/server/name fields appear in the output |

**Totals:** Phase 1 = 18 h · Phase 2 = 2 h

## 6. Testing (see [X2](X2-testing-quality-governance.md))

- Unit tests (on fake MT5): emit-on-`time_msc`-change, back-fill dedupe, bar reconcile replacing in-progress bars, UTC conversion (incl. DST transitions of the broker offset), supervisor backoff schedule, allowlist wrapper.
- Contract tests: every published message validates against `sd_contracts`.
- Soak test (manual, real terminal): 24 h run reusing `P0-WP06`'s log analyzer.

## 7. Exit criteria

These support Phase 0 *"24 h run without manual intervention"* and Phase 1 *"Live chart latency <300 ms; gap-free M1 for watched symbols"*. Measurable gateway-side checks:

- [ ] Gateway-side tick latency (MT5 `time_msc` → XADD) p99 < 150 ms with `POLL_MS=150`.
- [ ] In a 24 h soak, there are zero M1 gaps during market hours for watched symbols, as verified against `copy_rates_range` after the fact.
- [ ] Recovers from a forced terminal restart with no manual action and no data gap after back-fill.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `-10005` IPC timeouts (reported on 5.0.6231 / Py 3.13) | Single thread, sequential calls, Python 3.12, same privilege level, supervisor + back-fill, pinned package version |
| Package releases break the API (frequent cadence) | Pin the exact version in `apps/gateway/pyproject.toml`. Upgrade only deliberately, after a 24 h soak on the new version |
| History truncated by "Max bars in chart" / broker depth | Surface the `truncated` flag. Runbook: raise "Max bars in chart" and restart the terminal. Accept the broker's limits |
| Demo account expiry | Credentials live in `.env`. Health shows `login_failed`. Runbook covers re-login |
| Broker symbol suffixes (`EURUSD.m`) | `sd_core.symbols` keeps a canonical↔broker symbol map, populated from `symbols_get` |

## 9. Open questions / verify at build time

- The latest `MetaTrader5` version on PyPI at build time. Keep the P0 pin unless there is a reason to change it.
- Whether your broker demo exposes DOM (`market_book_*`). It is not needed until later, and is optional.
- Whether investor-password logins can stream data on your broker. If so, use them.
