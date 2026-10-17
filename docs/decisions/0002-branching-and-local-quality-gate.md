# ADR 0002 — `development` integration branch and a local quality gate (no GitHub CI)

- **Status:** accepted
- **Date:** 2026-10-17
- **Decided by:** Ruben Bezuidenhout
- **Affects:** CLAUDE.md (Git), `.claude/` (rules, skills, guard hook), `.githooks/`, X2 (§4.5, WP03/06/08), README decision log D15/D16

## Context

The repo is hosted privately at `github.com/RubzB12/tradingcoach`. Two facts changed how it is run:

1. All work should go into a dedicated `development` branch instead of straight onto `main`.
2. There are **no GitHub Actions minutes left**, so CI workflows cannot run.

The earlier plans treated GitHub CI as the authoritative backstop for the project's invariants (no order code, MT5 only in the gateway, deliberate-only Claude API, no secrets in the browser, honest validation). Without it, those checks must still run somewhere that cannot be skipped by accident.

## Decision

**Branching**
- `development` is the integration branch. All work is done on `wp/<WP-ID>-<slug>` or `chore/<slug>` branches **cut from `development`**.
- A finished branch is merged into `development` locally with `git merge --no-ff`, after `/wp-done` passes and the user approves. `development` is pushed only when asked.
- `main` is updated only at **phase boundaries**, by `/phase-review`, via `git merge --no-ff development`, with an optional tag `phase-<P#>-complete`.
- No direct commits on `development` or `main`. This is enforced by the Claude guard hook (`git commit` is blocked on both branches, except while concluding a merge).

**Quality gate (replaces CI)**
- **`just check`** runs lint, the structural/invariant tests, unit tests and the contract drift check, in under about 2 minutes.
- **`.githooks/pre-push`** runs it on every push and blocks the push on failure. Enabled per clone by `git config core.hooksPath .githooks` (`just hooks`). It falls back to the structural tests alone until the justfile exists.
- Heavier suites run on demand: `just test-db`, `just test-integration`, `just test-leakage`, `just test-e2e`.
- `/wp-done` runs `just check` independently of the hook, and the edit-time guard (`.claude/hooks/guard_invariants.py`) still blocks violations as Claude writes them.
- `--no-verify` is forbidden (CLAUDE.md).
- No `.github/workflows/` directory is created.

## Consequences

- **Good:** no dependence on paid CI minutes, fast feedback, and the invariants stay enforced from Phase 0.
- **Weaker than CI:** a local gate can be skipped (`--no-verify`, or a fresh clone that hasn't run `just hooks`). Mitigated by the CLAUDE.md rule, `/wp-done` running the gate itself, and the edit-time guard.
- Only one machine runs the checks, so a failure that depends on a different OS or toolchain version would go unnoticed.
- Heavier suites (integration, leakage, E2E) are manual, so they depend on `/wp-done` running the ones each WP names.
- The tracker and plans record work by branch name, which still works under this flow.

## Alternatives considered

- **GitHub Actions** — preferred in principle (cannot be skipped), but unavailable now. The workflow designs are preserved in X2 Appendix A.
- **Pull requests into `development`** — adds a review UI, but needs the `gh` CLI or manual steps in the browser, and gives no gate without CI. A local `--no-ff` merge gives the same one-merge-per-WP history.
- **Squash merges** — cleaner history, but loses the individual commits inside each WP.
- **Committing directly on `development`** — less friction, but the history becomes harder to review and the guard can't separate WP work from chores.

## Re-enabling GitHub Actions later

1. Add `.github/workflows/ci.yml` that checks out the repo, installs uv/pnpm/just, and runs `just check`. Add `integration.yml` and `leakage.yml` for the heavier targets, using the designs in X2 Appendix A.
2. Set `development` (and `main`) branch protection to require the `ci` check.
3. Keep `.githooks/pre-push`, because it gives faster feedback before the push.
4. Add a new decision log row and update this ADR's status to *superseded*.
