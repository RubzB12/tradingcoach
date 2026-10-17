---
paths:
  - "packages/sd_contracts/**"
  - "apps/backend/realtime/**"
  - "apps/web/lib/ws-client.ts"
  - "apps/web/lib/contracts/**"
  - "apps/web/stores/**"
---

# Realtime and contract rules

- **Single source of truth:** every stream message and WS payload is a pydantic model in `packages/sd_contracts`. TypeScript types are generated from it and never written by hand.
- **To change or add a message:**
  1. Edit `sd_contracts`.
  2. Run `just contracts`.
  3. Commit both the Python and the generated `apps/web/lib/contracts/{api,ws}.ts`.

  `just check` fails on drift.
- **Never hand-edit** `apps/web/lib/contracts/*`. A permission rule denies it, and the hook guard blocks it.
- **Server→client envelope is fixed:** `{channel, symbol, tf, seq, ts, payload}`. To add a channel, add a new `channel` literal and payload model. Never overload an existing payload.
- **Client→server ops:** `subscribe`, `unsubscribe` and `ping` only. Validate them; an invalid op gets an error frame and must never crash the consumer or add it to a group.
- **Groups** are named `sym.<SYMBOL>.tick`, `sym.<SYMBOL>.bar.<TF>`, `signals`, `health` and `alerts`. Sanitise symbols to `[A-Za-z0-9._-]`.
- **Sequencing:** `seq` is assigned per (channel, symbol, tf) **only** by `stream_fanout`. The client treats a gap as a reason to resync via REST.
- **Throughput:** coalesce ticks to the latest per symbol every 100 ms in `stream_fanout`. msgpack framing is opt-in (`?format=msgpack`).
- **Latency fields:** keep `src_ts` (MT5 `time_msc`) and `gw_ts` on tick and bar envelopes. P1's latency exit check depends on them.
- **UI fan-out never waits on DB writes.** Fan-out and ingest use separate consumer groups.

See: `docs/plans/F1-backend-platform-django.md` §4.7, §4.10; `docs/plans/P1-data-and-live-charts.md` §4.2.
