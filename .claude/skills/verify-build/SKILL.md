---
name: verify-build
description: Check a SignalDeck plan's "verify at build time" items (library versions, APIs, model IDs, prices) against current sources and report what changed. Use before starting a phase or a WP that depends on fast-moving libraries (Next.js, Lightweight Charts, Django Ninja, MetaTrader5, TA-Lib, foundation models, the Claude API).
argument-hint: <plan ID, e.g. F3 or P4 or X1>
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Skill
---

# Verify build-time assumptions for `$ARGUMENTS`

1. Open `docs/plans/$ARGUMENTS-*.md`. Collect every item from **§9 Open questions / verify at build time**, plus the version or API claims in §4 that the items rely on (e.g. "Next.js 16 `proxy.ts`", "Lightweight Charts v5 primitives", "TimescaleDB image tag").

2. Check each item against an authoritative, current source:
   - **Python packages:** `https://pypi.org/pypi/<package>/json` (latest version, release date, Python/wheel support, e.g. win_amd64 for MetaTrader5 and TA-Lib).
   - **npm packages:** `https://registry.npmjs.org/<package>/latest`, plus the package's release notes for breaking changes.
   - **Docker images:** the image's registry tags page.
   - **Claude API items** (model IDs, prices, `output_config`, effort, caching, batches, web search): **load the `claude-api` skill** and use its references. Don't rely on memory.
   - **Framework behaviour** (Next.js, Django, Channels, Ninja, Celery, TimescaleDB): official docs or changelogs.

   Prefer official sources over blogs, and note the source URL and date for each item.

3. Report a table: `Item | Plan says | Current reality (source, date) | Impact | Proposed change`. Mark the impact as `none`, `minor` (version bump) or `breaking` (API or behaviour change that affects a WP).

4. For `minor` and `breaking` items, propose exact edits to the plan section (and to the `.claude/rules/` file if a rule mentions the outdated detail). **Don't apply edits silently.** Show them and apply only after the user approves. Breaking changes also need a README decision-log entry (`.claude/rules/docs-plans.md`).

5. Never install or upgrade dependencies as part of this skill. It only verifies and proposes.
