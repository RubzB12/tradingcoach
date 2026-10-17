---
name: wp-start
description: Start a SignalDeck work package — load its plan and acceptance criteria, check dependencies in TRACKER.md, create the wp/ branch and mark it doing. Use when the user says to start or implement a WP ID such as P1-WP02.
argument-hint: <WP-ID, e.g. P1-WP02>
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit, Bash(git status *), Bash(git status), Bash(git switch *), Bash(git checkout -b wp/*), Bash(git branch *), Bash(git rev-parse *), Bash(git fetch *), Bash(git fetch), Bash(git pull --ff-only), Bash(git pull --ff-only *)
---

# Start work package `$ARGUMENTS`

Follow these steps in order. Stop and report to the user if any step fails.

1. **Resolve the WP.**
   - The ID must match `^(F[1-3]|P[0-5]|X[12])-WP\d{2}$`. If it doesn't, stop and ask.
   - Find the plan file: Glob `docs/plans/<prefix>-*.md`, where `<prefix>` is the part before `-WP`.
   - Read the WP's row in that plan's **§5 Work packages** table: task, estimate, priority, depends-on and **acceptance criteria**.

2. **Load the design context.**
   - Read the plan sections the WP depends on: §4 Design (the parts relevant to this task), §6 Testing and §9 Verify-at-build-time.
   - For each dependency, read its row too, so you know what it provides.
   - Don't read the whole plan set. Read only what this WP needs.

3. **Check the tracker.**
   - In `docs/plans/TRACKER.md`, find this WP's row and every dependency's row. A dependency written as `WP03` in the plan means `<prefix>-WP03`; phase dependencies like `P0` mean every `M` WP of that phase.
   - If the WP is already `done`, stop and say so.
   - If any dependency is not `done`, list them with their status and **ask the user** whether to proceed anyway. Don't continue until they answer.

4. **Prepare git.**
   - Run `git status`. If the tree has uncommitted changes, stop and ask the user how to handle them. Never stash or discard on your own.
   - `development` is the integration branch, and **WP branches are always cut from it**. Run `git switch development` and then `git pull --ff-only` (if it can't fast-forward, stop and report, and never merge or reset on your own).
   - Create and switch to `wp/<WP-ID>-<short-kebab-slug>` from `development`, with the slug taken from the task title (≤ 5 words). If that branch already exists, switch to it instead, because the work is being resumed.
   - Never start work on `main` or `development` itself. Commits there are blocked by the guard hook.

5. **Mark it started.** In `TRACKER.md`, set this WP's Status to `doing` and Started to today's date (YYYY-MM-DD). Change nothing else.

6. **Reply with an implementation outline:**
   - the goal in one sentence
   - the acceptance criteria as a checklist, each paired with how it will be verified (test, command, measurement)
   - the files and modules you expect to create or touch, with the `.claude/rules/` files that will apply
   - any §9 "verify at build time" items relevant to this WP, and the claude-api skill if Anthropic SDK code is involved
   - risks or open questions

   Then start implementing, unless the user asked for the outline only.

Reminders: stay inside this WP's scope (note follow-ups in the tracker Notes column). Respect the CLAUDE.md invariants. Finish with `/wp-done`.
