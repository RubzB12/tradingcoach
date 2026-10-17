# P0 — Spike: MT5 Connectivity

> **Type:** Phase · **Master effort:** 1 wk · **This plan:** 12 h
> **Master plan refs:** Roadmap Phase 0; §1 MT5 integration; Recommendation 1 ("Decide the MT5 host first")
> **Index:** [README](README.md)

## 1. Goal and context

This phase proves that a Python process can reliably read live data from your MT5 terminal on this Windows machine, survive disconnects, and handle time zones correctly, all **before** any platform work starts.

The spike code is deliberately small. It becomes the seed of the production gateway ([F2](F2-mt5-gateway.md)). It also records real ticks, which the fake MT5 replays for tests.

## 2. Scope

**In:** terminal + demo setup, pinned Python env, tick polling for 3 symbols, reconnect loop, UTC handling, 24 h soak harness + analyzer, tick recordings.

**Out:** Redis, Django, the UI and storage. Output is stdout plus JSONL/Parquet files only.

## 3. Dependencies

None. This is the first phase.

**Decision recorded here:** the MT5 host is **native Windows 11** (this machine). Record it in `docs/decisions/0001-mt5-host.md`.

## 4. Design

```
apps/gateway/spike/
  spike.py          # init → login → select symbols → poll loop → JSONL + Parquet
  timeutil.py       # broker-offset detection, to_utc(), tz-aware helpers  (→ moves to sd_core.time in F2)
  analyze_soak.py   # reads JSONL log → report: gaps, errors by code, reconnects, poll-lag percentiles
data/recordings/{SYMBOL}/{YYYY-MM-DD}.parquet   # raw ticks for fake MT5 (F2-WP06)
data/logs/spike-*.jsonl
```

**Poll loop:**

```
initialize(timeout=60000) → login → for sym: symbol_select(sym, True)
every 150 ms: for sym: t = symbol_info_tick(sym); if t is None → handle(last_error())
             if t.time_msc > last[sym]: log + buffer
every 60 s:  flush Parquet; log heartbeat (lag p50/p99, ticks/min per symbol)
on -10005/-10003/-10004: shutdown → backoff 1..60 s → initialize/login → copy_ticks_from(last) back-fill
```

**Time handling:**

- Tick `time`/`time_msc` are seconds/ms since epoch in **broker server time** labelled as UTC ("without the shift").
- Detect the offset with `round((latest_tick_time - utc_now) / 3600)` during active market hours. Store it and log every hour, so DST changes are visible.
- Every datetime passed into `copy_*` is built tz-aware in UTC.

**Suggested symbols:** EURUSD, GBPUSD, USDJPY. If your broker offers one, add an equity CFD later to see session-hour behaviour.

## 5. Work packages

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| P0-WP01 | **Terminal + broker demo:** install MT5, open a broker demo (not MetaQuotes-Demo), set "Max bars in chart" high and restart, add symbols to Market Watch, note symbol suffixes, confirm the "algo trading via external Python API" setting needed for connection; write `docs/decisions/0001-mt5-host.md` | 1.5 | M | — | Terminal logged in, 3 symbols streaming in Market Watch, decision record written |
| P0-WP02 | **Python env + pin:** `uv venv --python 3.12` in `apps/gateway`, `MetaTrader5==<latest at build>` pinned, smoke script printing `terminal_info()`, `account_info()` (redacted), `version()` | 1.5 | M | WP01 | Smoke script runs; versions recorded in the decision record |
| P0-WP03 | **Tick polling:** 150 ms loop for 3 symbols, emit on `time_msc` change, JSONL log, per-minute heartbeat with lag stats | 2 | M | WP02 | Ticks print for all 3 symbols with no duplicates over 30 min |
| P0-WP04 | **UTC handling:** `timeutil.py` (offset detection, `to_utc`, tz-aware builders), unit tests incl. a DST-transition case, cross-check one bar against the terminal chart | 2 | M | WP03 | Tests pass; logged bar open times match the chart once the offset is applied |
| P0-WP05 | **Reconnect loop:** error wrapper using `last_error()`, backoff, re-init, re-select, `copy_ticks_from` back-fill since last `time_msc`; manual tests: close the terminal, disconnect the network, log out | 2 | M | WP03 | Each manual fault recovers on its own, and back-fill covers the outage window (verified with the analyzer) |
| P0-WP06 | **Soak harness + analyzer:** run as a background process with log rotation; `analyze_soak.py` reports gaps > 5 s in market hours, error counts by code, reconnects, lag p50/p99, memory growth | 2 | M | WP05 | Analyzer report produced for a ≥ 24 h run |
| P0-WP07 | **Tick recordings:** buffered Parquet writer (`data/recordings/…`), with a schema matching F2's `TickMsg` | 1 | M | WP03 | ≥ 1 trading day of Parquet recordings per symbol exists for fake MT5 |

**Total:** 12 h

## 6. Testing

- `timeutil` unit tests, which later move to `sd_core` tests.
- The manual fault-injection checklist from P0-WP05, recorded in the decision record.
- The soak analyzer is the test for the exit criterion.

## 7. Exit criteria

**Master:** *"24 h run without manual intervention."*

Measurable checks:

- [ ] Continuous ≥ 24 h run on a weekday, with no human intervention.
- [ ] Zero unrecovered errors. Every reconnect recovers within 2 min.
- [ ] No tick gaps > 5 s for EURUSD during the London/NY sessions after back-fill, with the analyzer report attached to `docs/reports/p0-soak.md`.
- [ ] Poll lag p99 < 500 ms. Memory growth < 50 MB over 24 h.
- [ ] Decision record lists: host, terminal build, `MetaTrader5` version, Python version, broker, broker UTC offset, symbol suffixes.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `-10005` IPC timeouts | Same privilege level for terminal and Python (neither elevated), Python 3.12, single thread. If it persists, try the previous package version |
| Terminal auto-updates mid-soak | Note the build in the report. If an update interrupts the run, restart the soak |
| Weekend start gives a meaningless soak | Start Monday–Thursday. FX closes Friday evening |
| Windows sleep/hibernate | Set the power plan to never sleep during the soak |

## 9. Open questions / verify at build time

- Which broker demo to use. It should offer realistic spreads, the symbols you care about (FX + some stock CFDs) and a long demo validity.
- The current `MetaTrader5` version on PyPI.
