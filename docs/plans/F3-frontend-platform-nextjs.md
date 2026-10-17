# F3 — Frontend Platform (Next.js 16)

> **Type:** Foundation · **Scheduled in:** Phase 1
> **Master plan refs:** §5 Visualization and animation (library table, "keep tick updates out of React state"), §2 Monorepo (`apps/web`), Key Finding 6 (Next.js 16 / Lightweight Charts v5 / Motion)
> **Index:** [README](README.md)

## 1. Goal and context

This plan sets up the dashboard shell and the shared client infrastructure that every feature reuses:

- a typed REST client
- one multiplexed WebSocket per tab
- streaming state kept outside React render
- a Lightweight Charts v5 wrapper that updates imperatively at ≤ 30 fps
- the animation and design system

The browser talks **only** to Next.js, which proxies `/api/*` and `/ws/*` to Django. That keeps session cookies same-origin, and no secret ever reaches the client.

## 2. Scope

**In:** app scaffold, styling and components, routing skeleton, proxy/rewrites, CSRF-aware fetch, API types, TanStack Query, ws-client, Zustand stores, chart wrapper + primitive registry, Motion/Sonner/cmdk, health banner, frontend test setup.

**Out:** feature pages and components (symbol page P1, backtests P2, explainability P3, advisor X1, monitoring P5).

## 3. Dependencies

- [F1-WP05](F1-backend-platform-django.md#5-work-packages): API root and session auth
- [F1-WP04](F1-backend-platform-django.md#5-work-packages): WS consumer
- [F1-WP08](F1-backend-platform-django.md#5-work-packages): generated TS contracts

## 4. Design

### 4.1 Stack (verify versions at install)

`next@16` (App Router, Turbopack default) · `react@19` · TypeScript strict · `tailwindcss@4` · `shadcn/ui` · `lightweight-charts@5` · `echarts` + `echarts-for-react` (explainability, P3) · `@visx/*` (bespoke SVG, as needed) · `motion` (`motion/react`) · `zustand` · `@tanstack/react-query` · `openapi-fetch` (typed client over `openapi-typescript` output) · `sonner` · `cmdk` · `msgpackr` (optional binary WS) · `lottie-react` (optional) · Plotly lazy-loaded (research views only).

### 4.2 Directory layout (`apps/web`)

```
app/
  layout.tsx                  # providers: QueryClient, theme, Toaster, WS provider
  (auth)/login/page.tsx       # posts to Django session login via proxy
  (dashboard)/layout.tsx      # sidebar nav, header (symbol search ⌘K, health banner)
  (dashboard)/page.tsx        # overview / watchlist
  (dashboard)/symbols/[symbol]/page.tsx
  (dashboard)/signals/page.tsx
  (dashboard)/backtests/page.tsx · backtests/[id]/page.tsx
  (dashboard)/models/page.tsx
  (dashboard)/advisor/page.tsx        # history across symbols (X1)
  (dashboard)/monitoring/page.tsx     # P5
  (dashboard)/settings/page.tsx
components/
  ui/            # shadcn generated
  charts/        # PriceChart, chart-core (wrapper), primitives/ (regime bands, SL/TP zones, fan, dashed levels)
  explain/       # P3: ShapWaterfall, RollingShap, ConfidenceGauge, ThinkingStepper, Reliability
  pipeline/      # P2/P3: PipelineGraph
  signals/       # P2: SignalCard, SignalFeed
  advisor/       # X1: AskClaudeButton, PreviewDrawer, ResultCard, ...
  system/        # HealthBanner, ConnectionDot, CommandPalette
lib/
  contracts/api.ts, ws.ts     # GENERATED — do not edit
  api.ts                      # openapi-fetch client + CSRF header
  ws-client.ts                # multiplexed socket
  sse.ts                      # fetch-stream SSE parser (POST-capable)
  format.ts                   # price/time formatting by symbol digits
stores/
  ticks.ts, bars.ts, signals.ts, health.ts, ui.ts
queries/
  keys.ts, symbols.ts, bars.ts, signals.ts, backtests.ts, models.ts, settings.ts
proxy.ts                      # Next 16 (formerly middleware.ts): redirect to /login if no sessionid cookie
next.config.ts                # rewrites → Django
```

### 4.3 Proxying and auth

- `next.config.ts` rewrites `/api/:path*` → `http://localhost:8000/api/:path*`, and `/ws/:path*` → Django.
  - If dev-server WS rewrites prove unreliable, the client connects directly to `ws://localhost:8000/ws/`. In that case Django adds `localhost:3000` to `ALLOWED_HOSTS` and the Channels `AllowedHostsOriginValidator` config.
- `proxy.ts` only checks that a session cookie exists and redirects to `/login` if it doesn't. Django remains the real auth authority.
- `lib/api.ts` reads the `csrftoken` cookie and sends `X-CSRFToken` on unsafe methods.

### 4.4 State split (master §5 "State")

| Data | Where | Why |
|---|---|---|
| Ticks, forming bars, live signals, health, pipeline events | **Zustand** stores with fixed-size ring buffers (`Float64Array`-backed for ticks) | Very frequent updates. Components subscribe to narrow selectors. Charts read via `store.subscribe` outside React |
| History bars, symbol metadata, signal ledger pages, backtests, models, settings, advisor history | **TanStack Query** | Cacheable server state, invalidated by WS events (e.g. `signal` resolution → invalidate `['signals']`) |
| UI state (selected symbol, tf, panel toggles) | Zustand `ui` store, persisted with `localStorage` wrapped in try/catch | Restores the per-user view |

### 4.5 ws-client contract

- There is one `WebSocket` per tab, created in `WSProvider`.
- The API is `subscribe(channel, {symbol, tf}, handler) → unsubscribe`. It reference-counts subscriptions and sends the `subscribe` op only for the first subscriber.
- **Reconnect:** exponential backoff (0.5 → 10 s), then re-subscribe to all active subscriptions.
- **Sequence tracking:** sequence numbers are tracked per (channel, symbol, tf). On a gap or a reconnect, it emits `resync` for that key, and the bars store refetches the tail via REST and merges it.
- Heartbeat `ping` every 15 s. Connection status is exposed to the `ConnectionDot`.
- Payloads are typed by the generated `ws.ts` discriminated union on `channel`.

### 4.6 Chart wrapper (`components/charts/chart-core.ts`)

- `createPriceChart(container, opts)` returns a controller with `setHistory(bars)`, `upsertBar(bar)`, `addPane(id)`, `addSeries(paneId, type, opts)`, `addPrimitive(paneId, primitive)` and `destroy()`.
- **Imperative update loop:** it subscribes to the bars/ticks store and coalesces updates into a `requestAnimationFrame` loop capped at 30 fps. It calls `series.update()` and never re-renders React per tick.
- It handles resize via `ResizeObserver`, theme tokens from CSS variables (light/dark), and price formatting from `symbol.digits`.
- **Primitive registry:** typed interfaces for the primitives that later phases add — `RegimeBands` (P3), `BarrierBox` / SL-TP zones (P2/P3), `FanChart` (P4), `DashedLevels` (X1 "Show on chart"), and `AttentionHeatmap` pane (P4).
- The React component `<PriceChart symbol tf panes />` is a thin client component around the controller.

### 4.7 Motion, feedback and design

- `LazyMotion` with `domAnimation` features, for bundle size. Shared variants live in `lib/motion.ts` (stagger, pulse, packet-travel).
- Sonner toasts. The browser Notifications API is wrapped in `lib/notify.ts` (permission prompt from Settings, never on load).
- cmdk palette (⌘K): symbol search (`GET /symbols?q=`) and navigation.
- `HealthBanner`: shows a "Feed stale" or "Gateway reconnecting" banner from the `health` channel, with a REST `/health` poll fallback every 10 s when the WS is down.

## 5. Work packages

| ID | Task | Est. h | Pri | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| F3-WP01 | **Scaffold:** `create-next-app` (App Router, TS, Tailwind v4), shadcn init, theme tokens (light/dark), `(dashboard)` layout with sidebar + header, route stubs | 3 | M | F1-WP01 | `pnpm dev` runs on Turbopack, all route stubs render, and dark mode toggles |
| F3-WP02 | **Proxy + auth:** rewrites to Django, `proxy.ts` session guard, login page, CSRF-aware `lib/api.ts` | 2 | M | WP01, F1-WP05 | Login → dashboard works, and `PUT /api/v1/settings` succeeds with CSRF from the browser |
| F3-WP03 | **Typed API + Query:** `openapi-fetch` client from generated `api.ts`, QueryClient provider, `queries/keys.ts` conventions, error toast on API error envelope | 2 | M | WP02, F1-WP08 | A type error appears in the IDE when the backend schema changes and `just contracts` is re-run |
| F3-WP04 | **ws-client:** provider, ref-counted subscribe, reconnect + resubscribe, per-key seq tracking + resync events, ping, typed handlers, optional msgpack | 3 | M | WP01, F1-WP04 | After killing and restarting `backend`, subscriptions resume automatically, and an injected seq gap triggers a resync |
| F3-WP05 | **Zustand stores:** ticks (ring buffer), bars (per symbol/tf, forming bar), signals, health, ui (persisted with try/catch) | 2 | M | WP04 | 1,000 ticks/s synthetic load causes no React re-renders in unrelated components (React Profiler) |
| F3-WP06 | **Chart wrapper:** `chart-core` controller, rAF ≤ 30 fps loop, panes, resize, theme, `<PriceChart>`, primitive interface + one sample primitive (horizontal band) | 4 | M | WP05 | With synthetic 50 ticks/s, the chart stays smooth and the main thread is < 30% busy (Performance panel) |
| F3-WP07 | **System UX:** LazyMotion + shared variants, Sonner, cmdk palette (symbol search), `HealthBanner`, `ConnectionDot` | 2 | S | WP04 | The banner appears within 10 s of stopping the gateway, and ⌘K finds symbols |
| F3-WP08 | **Frontend test setup:** Vitest + Testing Library config, MSW for REST mocks, a mock WS server helper, Playwright config targeting the compose `offline` profile | 2 | S | WP01 | `pnpm test` runs in `just check` and `pnpm e2e` via `just test-e2e` (X2-WP03) |

**Totals:** Phase 1 = 20 h

## 6. Testing (see [X2](X2-testing-quality-governance.md))

- Vitest: ws-client (reconnect, ref-counting, seq gap), ring buffer, formatters, CSRF header.
- Playwright (X2-WP07): login → symbol page → live candle updates against the fake gateway.
- Visual regression on `<PriceChart>` with fixed fixture data (X2-WP07).

## 7. Exit criteria

These support Phase 1 *"Live chart latency <300 ms"*. Measurable checks:

- [ ] Client-side render latency (WS receive → `series.update`) p95 < 40 ms at 30 fps.
- [ ] No tick-rate data stored in React state (code review check + Profiler).
- [ ] The browser never receives API keys. `grep -r NEXT_PUBLIC_ apps/web` shows no secrets (X2 test).

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| WS proxy via Next dev rewrites is flaky | Use a direct WS to `:8000` with an origin allowlist (documented fallback) |
| Lightweight Charts v5 primitive API changes | Isolate everything behind `chart-core`. Pin the minor version |
| Bundle bloat (ECharts, Plotly) | `next/dynamic` imports for explainability and research views. Plotly is never on the symbol page's hot path |

## 9. Open questions / verify at build time

- Confirm the Next.js 16 `proxy.ts` API and the WebSocket rewrite support in Turbopack dev.
- Choose `openapi-fetch` or orval/hey-api codegen. The default is `openapi-fetch` (minimal).
