#!/usr/bin/env python3
"""PostToolUse hook: format the file Claude just wrote, if the formatter is installed.

- .py            -> `ruff format` + `ruff check --fix` (ruff must be on PATH)
- .ts/.tsx/.js   -> local prettier from apps/web/node_modules/.bin (never npx/network)
Skips generated contracts, docs and files outside the repo. Always exits 0.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or Path(__file__).resolve().parents[2])
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    path = Path(file_path)
    try:
        rel = os.path.relpath(os.path.normcase(str(path)), os.path.normcase(str(root))).replace("\\", "/")
    except ValueError:
        return 0
    if rel.startswith("..") or rel.startswith(("docs/", "apps/web/lib/contracts/")) or not path.exists():
        return 0

    cmds: list[list[str]] = []
    if path.suffix == ".py" and (ruff := shutil.which("ruff")):
        cmds = [[ruff, "format", "--quiet", str(path)], [ruff, "check", "--fix", "--quiet", str(path)]]
    elif path.suffix in (".ts", ".tsx", ".js", ".jsx", ".css"):
        bin_dir = root / "apps" / "web" / "node_modules" / ".bin"
        for name in ("prettier.cmd", "prettier"):
            if (bin_dir / name).exists():
                cmds = [[str(bin_dir / name), "--write", "--log-level", "warn", str(path)]]
                break

    for cmd in cmds:
        try:
            subprocess.run(cmd, cwd=root, capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
