---
paths:
  - "**/tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "apps/web/e2e/**"
---

# Testing rules

- **Never weaken, skip, `xfail` or delete a structural, leakage or contract test to make a build pass.** If one fails, the code is wrong, or the test needs a reviewed change explained in the commit message.
- **Markers:**
  - `unit` (default), `db` (real TimescaleDB) and `integration` (compose offline profile).
  - `live_mt5` and `live_claude` never run in `just check` and never run without asking you first (they need a terminal or cost money).
- **DB tests use real TimescaleDB** (a service container). Never SQLite: hypertables and continuous aggregates must actually be exercised.
- **Fakes, not mocks, at the boundaries:**
  - MT5 → `sd_gateway.fake_mt5` replaying `tests/fixtures/recordings/*.parquet`
  - Claude → `FakeAdvisorClient` with recorded responses
  - REST in the frontend → MSW
- **Determinism:** inject or freeze clocks (time-machine/freezegun, the fake gateway's clock). No `sleep`-based waits; assert eventual state with timeouts. Seed every RNG.
- **New structural or contract tests** must be shown failing on a deliberate violation once, on the branch that adds them.
- **ML tests** prove behaviour on small crafted series (barrier edge cases, purging overlaps, the DSR worked example). Parity tests (`barrier_sim` vs `paper_tracker`) must stay green.
- **Frontend:**
  - Vitest + Testing Library for units.
  - Playwright for E2E against the compose `offline` profile.
  - Visual regression only on fixed fixture data.
- **Fixtures:** small, curated and committed under `tests/fixtures/`. Never commit real account identifiers or `.env` values, and redact recorded API responses.
- **Speed budget:** unit tests under 60 s locally, and `just check` (the pre-push gate) under about 2 min. Anything slower gets the `integration` marker and runs via its own `just test-*` target.

See: `docs/plans/X2-testing-quality-governance.md` §4.
