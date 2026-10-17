#!/usr/bin/env python3
"""SessionStart hook: prints a short SignalDeck status block that is added to Claude's context.

Shows the current phase (from CLAUDE.md), work packages marked `doing`/`blocked` in
docs/plans/TRACKER.md, and the git branch + dirty-file count. Never fails the session.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def current_phase(r: Path) -> str:
    try:
        for line in (r / "CLAUDE.md").read_text(encoding="utf-8").splitlines():
            m = re.search(r"\*\*Current phase:\s*(.+?)\*\*", line)
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return "unknown (CLAUDE.md missing 'Current phase' line)"


def tracker_rows(r: Path) -> tuple[list[str], list[str]]:
    doing, blocked = [], []
    try:
        lines = (r / "docs" / "plans" / "TRACKER.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return doing, blocked
    for line in lines:
        if not line.startswith("| ["):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 10:
            continue
        wp_id = re.sub(r"\[([^\]]+)\].*", r"\1", cells[0])
        title, status, started, notes = cells[1], cells[6].lower(), cells[7], cells[9]
        if status == "doing":
            doing.append(f"{wp_id} - {title}" + (f" (since {started})" if started else ""))
        elif status == "blocked":
            blocked.append(f"{wp_id} - {title}" + (f": {notes}" if notes else ""))
    return doing, blocked


def git(r: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=r, capture_output=True, text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    r = root()
    doing, blocked = tracker_rows(r)
    branch = git(r, "rev-parse", "--abbrev-ref", "HEAD") or "(no git)"
    dirty = git(r, "status", "--porcelain")
    dirty_count = len(dirty.splitlines()) if dirty else 0

    print("SignalDeck session context")
    print(f"- Current phase: {current_phase(r)}")
    print(f"- Git branch: {branch}" + (f" ({dirty_count} uncommitted change(s))" if dirty_count else ""))
    if branch in ("main", "development"):
        print(f"- WARNING: on protected branch `{branch}`. Commits here are blocked. Create a branch before editing "
              "(/wp-start <WP-ID>, or `git switch -c chore/<slug>` from development).")
    print("- In progress: " + ("; ".join(doing) if doing else "none - start one with /wp-start <WP-ID>"))
    if blocked:
        print("- Blocked: " + "; ".join(blocked))
    print("- Workflow: /wp-start <ID> -> implement -> /wp-done. Plans: docs/plans/, tracker: docs/plans/TRACKER.md")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never break session start
        print(f"session_context hook error: {exc}", file=sys.stderr)
        sys.exit(0)
