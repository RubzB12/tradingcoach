---
name: wp-done
description: Close the current SignalDeck work package — verify every acceptance criterion with evidence, run the quality gate and the matching reviewer, update TRACKER.md, commit, and (with approval) merge into development. Use when the user says a WP is finished or asks to close it.
argument-hint: "[WP-ID] (defaults to the WP in the current wp/ branch name)"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit, Agent, Bash(git status *), Bash(git status), Bash(git diff *), Bash(git diff), Bash(git log *), Bash(git add *), Bash(git commit *), Bash(git rev-parse *), Bash(git switch *), Bash(just *), Bash(uv run *), Bash(pytest *), Bash(python -m pytest *), Bash(python -m unittest *), Bash(ruff *), Bash(pyright *), Bash(lint-imports *), Bash(pnpm run *), Bash(pnpm exec *)
---

# Close work package `$ARGUMENTS`

1. **Identify the WP.** Use `$ARGUMENTS`. If it's empty, parse it from the current branch (`wp/<WP-ID>-…`). If the current branch is `main` or `development`, stop: work must be on a WP branch. Re-read the WP's acceptance criteria from `docs/plans/<prefix>-*.md` §5.

2. **Review the change set.** Run `git status` and `git diff development...HEAD --stat`, plus the working-tree diff, so you know every file touched.

3. **Run the quality gate.** There is no GitHub CI, so this is the gate:
   - Run **`just check`** (lint, structural tests, unit tests, contract drift). Until the justfile exists (X2-WP03), run `python -m unittest discover -s tests/structural` and the WP's own tests directly (in P0, with `apps/gateway/.venv`).
   - Run any heavier suite the WP's criteria name (`just test-db`, `just test-integration`, `just test-leakage`, `just test-e2e`), and any WP-specific command: soak analyzer, latency/gap reports, migrations, benchmarks.
   - Never run `live_mt5`/`live_claude` tests, or anything that costs money, without asking.

4. **Run the matching reviewer subagent(s)** based on the paths changed, and fix or report every high-severity finding:
   - `apps/gateway/**`, `apps/backend/advisor/**`, `packages/sd_advisor/**`, settings or env handling → `invariants-reviewer`
   - `packages/sd_features|sd_labeling|sd_models|sd_backtest/**`, `apps/fm_worker/**`, `apps/backend/signals|mlops/**`, `research/**` → `leakage-reviewer`
   - `apps/web/**` charts/stores/ws-client, `apps/backend/realtime/**`, `stream_fanout` → `realtime-perf-reviewer`

5. **Report each acceptance criterion** in a table: `Criterion | Evidence (command output, test name, measurement, file) | PASS/FAIL`.
   - Be literal. A criterion that needs a 24 h run, a trading day of data or a manual check is `PENDING`, with what remains to be done. Don't pass it on assumption.
   - **If anything is FAIL or PENDING:** leave the tracker status as `doing` (or `blocked` with the reason in Notes), summarise what's left, and stop. Don't commit a "done" or merge.

6. **If everything passes, commit on the WP branch:**
   - Ask the user for actual hours spent. This is optional; leave it blank if they don't say.
   - Update `docs/plans/TRACKER.md` for this WP: Status `done`, Done = today (YYYY-MM-DD), Actual h, and the branch name in Notes (e.g. `wp/P1-WP02-ingest-streams`). Use the branch, not a commit hash, because hashes change on merge.
   - If the design changed during the WP, check that the plan section and the README decision log were updated (`.claude/rules/docs-plans.md`).
   - Stage only the files belonging to this WP, including the tracker, then commit with a conventional message: `feat(<WP-ID>): <summary>`, or `fix(…)`, `test(…)`, `chore(…)`, `docs(…)`. The body lists the acceptance criteria met. End with the attribution trailer.

7. **Merge into `development` — only with the user's approval.** Show a summary and ask. If approved:
   - `git switch development`, then `git merge --no-ff wp/<WP-ID>-<slug> -m "merge(<WP-ID>): <summary>"`. End the message with the attribution trailer. Never fast-forward, so that each WP stays visible as one merge.
   - If the merge conflicts: stop, report the conflicting files, and don't resolve them without the user.
   - Re-run `just check` on `development` if the merge brought in changes from elsewhere.
   - **Don't push** unless the user asks. When they do, `git push origin development` runs the pre-push gate, and if the gate fails, fix the cause and never use `--no-verify`.
   - Offer to delete the merged WP branch (`git branch -d`).

8. **Phase check.** If this was the last `M` WP of its phase in `TRACKER.md`, suggest running `/phase-review <phase>`.
