#!/usr/bin/env python3
"""PreToolUse guard for SignalDeck's non-negotiable invariants (see CLAUDE.md).

Modes
-----
default      Write/Edit hook: scans the new text against the target file path.
--command    Bash/PowerShell hook: scans write-like commands (redirects, heredocs,
             Set-Content, ...) for banned tokens. Read-only commands are never blocked.

Exit codes: 0 = allow, 2 = block (stderr is shown to Claude as the reason),
1 = guard error (non-blocking). CI structural tests (X2-WP02) remain authoritative;
this guard is the fast, edit-time layer. Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Paths that legitimately *describe* the bans (docs, rules, this guard, structural tests).
DESCRIPTIVE_PREFIXES = ("docs/", ".claude/", "tests/structural/")
DESCRIPTIVE_FILES = ("claude.md", "claude.local.md")

PY_EXT = (".py", ".pyi", ".ipynb")
JS_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

ORDER_RE = re.compile(r"\border_(send|check)\b")
MT5_IMPORT_RE = re.compile(
    r"^\s*(import\s+[^\n#]*\bMetaTrader5\b|from\s+MetaTrader5\b)"
    r"|(import_module|__import__)\(\s*['\"]MetaTrader5",
    re.MULTILINE,
)
CLAUDE_API_IMPORT_RE = re.compile(
    r"^\s*(import|from)\s+anthropic\b"
    r"|^\s*(import|from)\s+sd_advisor\.(client|request)\b"
    r"|^\s*from\s+sd_advisor\s+import\s+[^\n#]*\b(client|request)\b"
    r"|(import_module|__import__)\(\s*['\"](anthropic|sd_advisor\.(client|request))",
    re.MULTILINE,
)
ANY_ADVISOR_IMPORT_RE = re.compile(
    r"^\s*(import|from)\s+(sd_advisor|anthropic)\b"
    r"|(import_module|__import__)\(\s*['\"](sd_advisor|anthropic)",
    re.MULTILINE,
)
JS_ANTHROPIC_RE = re.compile(r"""(from\s+|require\(\s*|import\(\s*)['"]@anthropic-ai/""")
DJANGO_APPS = r"django|channels|ninja|config|core|marketdata|realtime|signals|paper|backtests|mlops|advisor|events|alerts|monitoring"
DJANGO_IMPORT_RE = re.compile(rf"^\s*(import|from)\s+({DJANGO_APPS})\b", re.MULTILINE)
DJANGO_OR_CELERY_IMPORT_RE = re.compile(rf"^\s*(import|from)\s+({DJANGO_APPS}|celery)\b", re.MULTILINE)
# Unanchored variants for shell commands, where code is embedded mid-line in quotes.
CMD_BANNED_IMPORT_RE = re.compile(
    r"\b(import|from)\s+(MetaTrader5|anthropic)\b|\bsd_advisor\.(client|request)\b|['\"]@anthropic-ai/"
)
NEXT_PUBLIC_SECRET_RE = re.compile(r"NEXT_PUBLIC_[A-Z0-9_]*(KEY|SECRET|TOKEN|PASSWORD)")
ANTHROPIC_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")

# Modules that run without a user click: they may not import sd_advisor at all.
BACKGROUND_RE = re.compile(
    r"(^|/)tasks\.py$|/management/commands/|^apps/backend/config/celery\.py$"
    r"|^apps/gateway/|^apps/fm_worker/|(^|/)flows?(/|\.py$)|_flow\.py$"
)
# Only these may import the Claude client (deliberate-only, X1 §6).
ADVISOR_ALLOWED_RE = re.compile(
    r"^packages/sd_advisor/|^apps/backend/advisor/(api|views|services)\.py$|^apps/backend/advisor/tests/"
)

WRITE_CMD_RE = re.compile(
    r"(?<![0-9&])>>?(?!\s*(/dev/null|\$null|&))"  # redirect (not 2>&1, >/dev/null, >$null)
    r"|\btee\b|<<|\bSet-Content\b|\bAdd-Content\b|\bOut-File\b|\bsed\s+-i\b|\bNew-Item\b[^\n]*-Value"
)
PROTECTED_CMD_TARGET_RE = re.compile(
    r"(>>?|Set-Content|Add-Content|Out-File|tee)\s*(-Path\s+|-FilePath\s+)?['\"]?(\./)?(\.env(\.local)?(?![\w.])|apps/web/lib/contracts/)"
)


def repo_root(payload: dict) -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    if payload.get("cwd"):
        return Path(payload["cwd"])
    return Path(__file__).resolve().parents[2]


def rel_path(file_path: str, root: Path) -> str | None:
    """Repo-relative, forward-slash, case-normalised path; None if outside the repo."""
    if not file_path:
        return None
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    try:
        rel = os.path.relpath(os.path.normcase(str(p)), os.path.normcase(str(root)))
    except ValueError:  # different drive on Windows
        return None
    rel = rel.replace("\\", "/")
    if rel.startswith("../") or rel == "..":
        return None
    return rel


def is_descriptive(rel: str) -> bool:
    return rel.startswith(DESCRIPTIVE_PREFIXES) or rel in DESCRIPTIVE_FILES


def new_text(tool_input: dict) -> str:
    parts: list[str] = []
    for key in ("content", "new_string", "new_source"):
        if isinstance(tool_input.get(key), str):
            parts.append(tool_input[key])
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
            parts.append(edit["new_string"])
    return "\n".join(parts)


def check_file(rel: str, text: str) -> list[str]:
    v: list[str] = []
    name = rel.rsplit("/", 1)[-1]

    # Protected targets (apply everywhere).
    if name in (".env", ".env.local") or (name.startswith(".env.") and name.endswith(".local")):
        v.append(f"Writing `{rel}` is blocked: secrets files are never edited by Claude. Edit `.env.example` (no real values) and ask the user to update `.env`.")
    if rel.startswith("apps/web/lib/contracts/"):
        v.append(f"`{rel}` is generated. Change the pydantic models in `packages/sd_contracts` (or the Ninja schemas) and run `just contracts`.")
    if ANTHROPIC_KEY_RE.search(text):
        v.append("Content contains what looks like an Anthropic API key (`sk-ant-...`). Keys live only in the backend `.env`, never in files Claude writes.")

    if is_descriptive(rel):
        return v

    if ORDER_RE.search(text):
        v.append("`order_send`/`order_check` found. SignalDeck never places trades (CLAUDE.md invariant 1) - remove it. MT5 access is read-only via `sd_gateway/mt5_client.py`.")
    if NEXT_PUBLIC_SECRET_RE.search(text):
        v.append("A `NEXT_PUBLIC_*KEY/SECRET/TOKEN/PASSWORD` variable would ship a secret to the browser (invariant 4). Keep secrets server-side in Django.")

    if rel.endswith(PY_EXT):
        if MT5_IMPORT_RE.search(text) and not rel.startswith("apps/gateway/"):
            v.append(f"`MetaTrader5` imported in `{rel}`. Only `apps/gateway/` may touch MT5 (invariant 1); consume gateway data from Redis/DB instead.")
        if BACKGROUND_RE.search(rel) and ANY_ADVISOR_IMPORT_RE.search(text):
            v.append(f"`{rel}` runs without a user click (task/command/scheduler/gateway/worker) and may not import `sd_advisor` or `anthropic` (deliberate-only, invariant 3).")
        elif CLAUDE_API_IMPORT_RE.search(text) and not ADVISOR_ALLOWED_RE.search(rel):
            v.append(f"Claude API client imported in `{rel}`. Only `apps/backend/advisor/{{api,views,services}}.py` and `packages/sd_advisor/` may import `anthropic`/`sd_advisor.client`/`sd_advisor.request` (invariant 3).")
        if rel.startswith(("apps/gateway/", "packages/")) and DJANGO_OR_CELERY_IMPORT_RE.search(text):
            v.append(f"Django/Celery/Django-app import in `{rel}`. The gateway and `packages/sd_*` must stay framework-free (invariant 2); move Django-specific code into `apps/backend/`.")
        elif rel.startswith("apps/fm_worker/") and DJANGO_IMPORT_RE.search(text):
            v.append(f"Django import in `{rel}`. The fm-worker uses Celery + `sd_*` packages only, never Django (P4 §4.1).")
    if rel.endswith(JS_EXT) and JS_ANTHROPIC_RE.search(text):
        v.append(f"`@anthropic-ai/*` imported in `{rel}`. The browser never calls Claude; the frontend talks only to Django `/api/v1/advisor/*`.")
    return v


def check_command(cmd: str) -> list[str]:
    v: list[str] = []
    stripped = cmd.lstrip()
    if stripped.startswith("git ") or not WRITE_CMD_RE.search(cmd):
        return v  # read-only or git (commit messages may legitimately mention the bans)
    if PROTECTED_CMD_TARGET_RE.search(cmd):
        v.append("This command writes to `.env`/`.env.local` or generated contracts. Secrets are user-managed; contracts come from `just contracts`.")
    if ANTHROPIC_KEY_RE.search(cmd):
        v.append("Command contains what looks like an Anthropic API key.")
    if ORDER_RE.search(cmd) or CMD_BANNED_IMPORT_RE.search(cmd) or NEXT_PUBLIC_SECRET_RE.search(cmd):
        v.append("This shell command writes content containing a banned token (order code, MetaTrader5/anthropic import, or NEXT_PUBLIC secret). Use the Write/Edit tool so path-aware invariant checks apply.")
    return v


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"guard_invariants: could not parse hook input ({exc}); allowing.", file=sys.stderr)
        return 1
    tool_input = payload.get("tool_input") or {}

    if "--command" in sys.argv[1:]:
        violations = check_command(str(tool_input.get("command") or ""))
    else:
        rel = rel_path(str(tool_input.get("file_path") or tool_input.get("notebook_path") or ""), repo_root(payload))
        if rel is None:
            return 0  # outside this repo
        violations = check_file(rel, new_text(tool_input))

    if violations:
        print("Blocked by .claude/hooks/guard_invariants.py (SignalDeck invariants, see CLAUDE.md):", file=sys.stderr)
        for item in violations:
            print(f"- {item}", file=sys.stderr)
        print("If you believe this is a false positive, stop and ask the user rather than working around the guard.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
