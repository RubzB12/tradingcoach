---
name: wp-done
description: Close the current SignalDeck work package — verify every acceptance criterion with evidence, run checks and the matching reviewer, update TRACKER.md and commit. Use when the user says a WP is finished or asks to close it.
argument-hint: "[WP-ID] (defaults to the WP in the current wp/ branch name)"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit, Agent, Bash(git status *), Bash(git status), Bash(git diff *), Bash(git diff), Bash(git log *), Bash(git add *), Bash(git commit *), Bash(git rev-parse *), Bash(just *), Bash(uv run *), Bash(pytest *), Bash(python -m pytest *), Bash(python -m unittest *), Bash(ruff *), Bash(pyright *), Bash(lint-imports *), Bash(pnpm run *), Bash(pnpm exec *)
---

# Close work package `$ARGUMENTS`

1. **Identify the WP.** Use `$ARGUMENTS`. If it's empty, parse it from the current branch (`wp/<WP-ID>-…`). Re-read its acceptance criteria from `docs/plans/<prefix>-*.md` §5.

2. **Review the change set.** Run `git status` and `git diff main...HEAD --stat`, plus the working-tree diff, so you know every file touched.

3. **Run the checks**, picking what exists at this stage of the project:
   - From F1-WP09 onward: `just lint` and `just test`, plus `just contracts` followed by a diff check if schemas changed.
   - Before that (P0): run the spike/gateway scripts or tests directly with `apps/gateway/.venv`.
   - Always run `python -m unittest discover -s tests/structural` (or `pytest tests/structural`).
   - Run any WP-specific command named in the acceptance criteria: soak analyzer, latency/gap reports, migrations, benchmarks.
   - Never run `live_mt5`/`live_claude` tests, or anything that costs money, without asking.

4. **Run the matching reviewer subagent(s)** based on the paths changed, and fix or report every high-severity finding:
   - `apps/gateway/**`, `apps/backend/advisor/**`, `packages/sd_advisor/**`, settings or env handling → `invariants-reviewer`
   - `packages/sd_features|sd_labeling|sd_models|sd_backtest/**`, `apps/fm_worker/**`, `apps/backend/signals|mlops/**`, `research/**` → `leakage-reviewer`
   - `apps/web/**` charts/stores/ws-client, `apps/backend/realtime/**`, `stream_fanout` → `realtime-perf-reviewer`

5. **Report each acceptance criterion** in a table: `Criterion | Evidence (command output, test name, measurement, file) | PASS/FAIL`.
   - Be literal. A criterion that needs a 24 h run, a trading day of data or a manual check is `PENDING`, with what remains to be done. Don't pass it on assumption.
   - **If anything is FAIL or PENDING:** leave the tracker status as `doing` (or `blocked` with the reason in Notes), summarise what's left, and stop. Don't commit a "done".

6. **If everything passes:**
   - Ask the user for actual hours spent. This is optional; leave it blank if they don't say.
   - Update `docs/plans/TRACKER.md` for this WP: Status `done`, Done = today (YYYY-MM-DD), Actual h, and the branch name in Notes (e.g. `wp/P1-WP02-ingest-streams`). Use the branch, not a commit hash, because hashes change on merge and recording one would mean amending.
   - If the design changed during the WP, check that the plan section and the README decision log were updated (`.claude/rules/docs-plans.md`).
   - Stage only the files belonging to this WP, including the tracker, then commit with a conventional message: `feat(<WP-ID>): <summary>`, or `fix(…)`, `test(…)`, `chore(…)`, `docs(…)`. The body lists the acceptance criteria met. End with the attribution trailer.
   - **Don't push or merge.** Tell the user the branch is ready to merge into `main`, and ask whether to do it.

7. **Phase check.** If this was the last `M` WP of its phase in `TRACKER.md`, suggest running `/phase-review <phase>`.
