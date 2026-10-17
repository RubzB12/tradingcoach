---
name: phase-review
description: Review a SignalDeck phase boundary — confirm all must-have WPs are done, gather evidence for the phase exit criteria, update the TRACKER summary and the CLAUDE.md current-phase line, and propose rule updates. Use when a phase's last WP closes.
argument-hint: <phase, e.g. P1>
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit, Bash(git status *), Bash(git status), Bash(git log *), Bash(git diff *), Bash(git add *), Bash(git commit *), Bash(git switch *), Bash(git checkout -b chore/*), Bash(just *), Bash(python -m unittest *), Bash(pytest *)
---

# Phase review: `$ARGUMENTS`

1. **Inventory.**
   - In `docs/plans/TRACKER.md`, list every WP scheduled in phase `$ARGUMENTS`, with its status.
   - If any `M` WP isn't `done`, list them and stop. The phase isn't ready. `S` WPs that aren't done must be `deferred`, with the target phase noted, and you need the user's agreement for each.

2. **Exit criteria.**
   - Open the phase plan (`docs/plans/$ARGUMENTS-*.md`) §7. For each master exit criterion and each measurable check, collect evidence: reports in `docs/reports/`, `just check` and other local test results, measurements. There is no GitHub CI.
   - Run any cheap verification commands needed.
   - Present a table: `Check | Evidence | PASS/FAIL/PENDING`. Don't mark the phase met unless every check passes.

3. **If the exit is met:**
   - Update the TRACKER **Summary** row for the phase: Done count, Actual h (the sum of the rows) and Exit met ✅.
   - Tick the phase's "Exit criteria met" box, with the date and evidence links.
   - Update the `**Current phase: …**` line in `CLAUDE.md` to the next phase name.
   - Update the README status note if one exists.

4. **Tidy CLAUDE.md:**
   - Once code exists, shrink the "Where things are" tree to only the non-obvious parts, since Claude can read the real tree.
   - Make sure the Commands table matches the `justfile`.
   - Keep the file under 150 lines.

5. **Lessons → rules.** Review the phase's commits, tracker notes and any repeated corrections the user made. Propose concrete one-line additions or edits to the **narrowest** matching `.claude/rules/*.md` file, or to CLAUDE.md only if the lesson applies everywhere. Show them as a diff and apply them only once the user approves.

6. **Re-estimate.** Compare actual vs estimated hours for the phase and suggest an adjustment factor for the remaining phases' estimates. Don't edit the estimates without approval.

7. **Commit** the tracker, CLAUDE.md and approved rule changes on a `chore/phase-review-$ARGUMENTS` branch, **cut from `development`**, with `docs(phase): close $ARGUMENTS`. Commits on `development` itself are blocked. Don't merge or push without asking.

8. **Promote to `main` (phase boundaries only, each step with the user's approval).**
   - First merge the `chore/phase-review-$ARGUMENTS` branch into `development` with `git merge --no-ff`, and run `just check` on `development`.
   - Then propose promoting: `git switch main`, `git merge --no-ff development -m "release($ARGUMENTS): phase complete"` (with the attribution trailer), and `git push origin main` and `git push origin development` (the pre-push gate runs, and never use `--no-verify`).
   - Optionally offer an annotated tag `phase-$ARGUMENTS-complete` (`git tag -a`), pushed only if the user asks.
   - Finish by switching back to `development`. `main` is never committed to directly, and is only ever changed by this merge.
