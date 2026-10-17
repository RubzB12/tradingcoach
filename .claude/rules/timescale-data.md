---
paths:
  - "apps/backend/marketdata/**"
  - "apps/backend/**/migrations/**"
  - "apps/backend/core/db*.py"
  - "apps/backend/core/migrations_ops*.py"
---

# TimescaleDB and market-data storage rules

- **Create hypertables in migrations** with the `core.migrations_ops` operations: `CreateHypertable`, `AddCompressionPolicy`, `AddRetentionPolicy`, `CreateContinuousAggregate`. Every operation needs a working reverse.
- **Primary keys:** time-series tables use `models.CompositePrimaryKey("symbol", "tf", "time")`, or `("symbol", "time_msc", "seq")` for ticks. Never add a surrogate `id` to a hypertable.
- **Bulk writes** go through `core.db.copy_rows` (psycopg 3 COPY into a staging table, then `INSERT … ON CONFLICT DO UPDATE`). Never use ORM `save()` loops or `bulk_create` for bars or ticks.
- **Timeframes:**
  - `M1`, `H4` and `D1` are stored straight from MT5 (`source='mt5'`). MT5's closed bar is authoritative.
  - `M5`, `M15` and `H1` are continuous aggregates over M1.
  - Never aggregate H4 or D1 yourself, because they align to broker midnight, not UTC.
  - Reads go through the `bars_all` view.
- **Ticks** are stored only for `Symbol.is_watched` symbols, subject to the retention policy (default 30 days). Bars are the long-term store.
- **Persist only final bars** (`final=true`). Forming bars are for the UI only.
- **Ingest:** commit first, then `XACK`, then emit `bars.persisted`. A restart must lose nothing and create no duplicates.
- **Precision:** prices are `numeric(18,8)`, rounded to `symbol.digits` at the API edge. Times are `timestamptz` in UTC.
- **Gap checks:** after back-fill or a gateway reconnect, the `/bars/{symbol}/gaps` report must be empty for market hours.
- **Parquet lake** layout is `data/lake/bars/symbol=…/tf=…/date=…/part.parquet`. It is written by the nightly export task, and research reads it through `sd_core.lake`.

See: `docs/plans/P1-data-and-live-charts.md` §4.1–4.2, `docs/plans/F1-backend-platform-django.md` §4.9.
