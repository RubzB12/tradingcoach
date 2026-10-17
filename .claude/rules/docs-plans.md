---
paths:
  - "docs/**"
---

# Documentation and planning rules

- **The plans in `docs/plans/` are the source of truth** for design and scope. Code follows the plans, and when reality forces a change, the plan is updated in the same branch.
- **WP IDs are permanent.** Never renumber or reuse them. New work gets the next free number in that plan, and you add it to `TRACKER.md` too.
- **Design changes** need three things:
  1. Update the affected plan section.
  2. Add a row to the README decision log (`D<next>`).
  3. If the change is significant, write an ADR at `docs/decisions/NNNN-<slug>.md` covering Context, Decision, Consequences and Alternatives considered.
- **TRACKER.md:**
  - Follow its "How to update" section.
  - Status values are `todo`, `doing`, `done`, `blocked` and `deferred`.
  - Fill in Started and Done dates (YYYY-MM-DD) and put the WP branch name in Notes.
  - Ask the user for Actual h; never invent it.
  - Update the phase summary row only from `/phase-review`.
- **Exit criteria:** the master-plan wording in each phase's §7 is never edited. The measurable checks below it may be refined, but only with a note explaining why.
- **Reports** (backtests, walk-forward, soak, FM eval, exit evidence) go in `docs/reports/<phase>-<topic>.md`, with dates, data ranges, cost assumptions and trial counts. Negative results are reported plainly.
- **No secrets or account identifiers** in any document, including screenshots and log excerpts.
- **Style:** concise, tables over prose where it helps, relative links between plan files, and exact plan section references (`F2 §4.5`).

See: `docs/plans/README.md`, `docs/plans/TRACKER.md`.
