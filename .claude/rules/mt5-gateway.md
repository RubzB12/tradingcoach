---
paths:
  - "apps/gateway/**"
---

# MT5 gateway rules

The gateway is the only code that talks to MetaTrader 5. It runs natively on Windows (`apps/gateway/.venv`, Python 3.12).

## Hard rules

- **Read-only, always.** No order code of any kind. The production code calls MT5 only through the allowlist in `sd_gateway/mt5_client.py`, so never add an order, position-modify or trade function to it. Demo accounts only.
- **No Django, no `anthropic`, no `sd_advisor`.** The gateway may import only `sd_core`, `sd_contracts`, the stdlib, `redis`, `pydantic`, `numpy`, `polars` and `MetaTrader5`.
- **One MT5Owner thread makes every MT5 call.** Other threads (publisher, request listener, watchdog) only touch `queue.Queue` and Redis. Never call MT5 from a second thread, an executor or asyncio.
- **Pinned `MetaTrader5` version.** Upgrading it needs a 24 h soak on the new version, recorded in `docs/decisions/0001-mt5-host.md`.

## Behaviour

- Poll `symbol_info_tick` every `POLL_MS` (default 150) and emit only when `time_msc` increases. Back-fill with `copy_ticks_from` every `BACKFILL_EVERY` cycles, deduping against the recent ring.
- At bar close (+1.5 s grace), publish **MT5's closed bar** from `copy_rates_from_pos(sym, tf, 0, 2)` with `final=true`. MT5's bar wins over the one built from ticks.
- **Time:** every datetime passed into MT5 is tz-aware UTC. Normalise broker server time on the way out with `sd_core.time`. Detect the broker offset at startup and publish it in health.
- **Errors:** wrap every call. A `None` return means read `last_error()`. On −10003/−10004/−10005: state `reconnecting` → `shutdown()` → exponential backoff with jitter (1→60 s) → `initialize()` → re-select symbols → back-fill from the last `time_msc`. Other errors: log, count and continue.
- Publish `gateway.health` every `HEARTBEAT_S` with a TTL'd `gateway:health` key. The watchdog exits non-zero if the owner loop stalls for > 10 s.
- History requests are chunked (≤ 50k rows per chunk) and must not stall tick polling (poll lag p99 < 500 ms).
- **Never publish or log credentials**, and strip login/server/name from `account_info` output.

## Fake MT5

- `sd_gateway/fake_mt5.py` must stay signature- and return-shape-compatible with every allowlisted function. When the real usage changes, update the fake in the same commit.
- Run tests with `--impl fake`. They never need a terminal.

See: `docs/plans/F2-mt5-gateway.md` (all), `docs/plans/P0-spike-mt5-connectivity.md` §4.
