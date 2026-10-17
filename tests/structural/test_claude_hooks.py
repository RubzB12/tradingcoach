"""Tests for .claude/hooks/guard_invariants.py (the edit-time invariant guard).

unittest-based so it runs before the uv workspace exists (`python -m unittest discover -s tests/structural`);
pytest collects it too. Payloads mimic Claude Code's PreToolUse stdin: absolute Windows-style paths.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / ".claude" / "hooks" / "guard_invariants.py"
SESSION = ROOT / ".claude" / "hooks" / "session_context.py"
FAKE_KEY = "sk-" + "ant-" + "a1b2c3d4e5" * 4  # assembled so this file never contains a literal key


PRE_PUSH = ROOT / ".githooks" / "pre-push"


def run_guard(payload: dict | str, *args: str, branch: str = "chore/test", merging: bool = False) -> subprocess.CompletedProcess[str]:
    """Run the guard with a pinned branch so results don't depend on the checked-out branch."""
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT), "SIGNALDECK_GUARD_BRANCH": branch}
    env.pop("SIGNALDECK_GUARD_MERGING", None)
    if merging:
        env["SIGNALDECK_GUARD_MERGING"] = "1"
    return subprocess.run([sys.executable, str(GUARD), *args], input=stdin, capture_output=True, text=True, env=env, timeout=10)


def write(rel: str, content: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Write",
            "tool_input": {"file_path": str(ROOT / rel), "content": content}}


def edit(rel: str, new: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Edit",
            "tool_input": {"file_path": str(ROOT / rel), "old_string": "x", "new_string": new}}


def command(cmd: str, tool: str = "Bash") -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": cmd}}


ORDER = "order" + "_send"  # keep the literal token out of non-exempt diffs of this file's history

BLOCKED_WRITES = [
    ("order code in gateway", write("apps/gateway/sd_gateway/x.py", f"mt5.{ORDER}(req)\n")),
    ("order_check via Edit", edit("apps/backend/signals/services.py", "r = mt5.order" + "_check(r)")),
    ("order code via getattr string", write("packages/sd_core/x.py", f"getattr(mt5, '{ORDER}')\n")),
    ("anthropic in celery task", write("apps/backend/signals/tasks.py", "import anthropic\n")),
    ("any sd_advisor in task", write("apps/backend/paper/tasks.py", "from sd_advisor.packet import build_packet\n")),
    ("sd_advisor in management command", write("apps/backend/signals/management/commands/bar_close_dispatcher.py", "from sd_advisor import config\n")),
    ("sd_advisor in gateway", write("apps/gateway/sd_gateway/loop.py", "import sd_advisor\n")),
    ("advisor client in non-advisor app", write("apps/backend/signals/api.py", "from sd_advisor.client import AnthropicAdvisorClient\n")),
    ("advisor client via from-import", write("apps/backend/core/services.py", "from sd_advisor import client\n")),
    ("dynamic anthropic import", write("apps/backend/core/util.py", "importlib.import_module('anthropic')\n")),
    ("MetaTrader5 outside gateway", write("apps/backend/marketdata/api.py", "import MetaTrader5 as mt5\n")),
    ("MetaTrader5 from-import in package", write("packages/sd_features/x.py", "from MetaTrader5 import copy_rates_range\n")),
    ("django in package", write("packages/sd_core/time.py", "from django.utils import timezone\n")),
    ("django app in gateway", write("apps/gateway/sd_gateway/x.py", "from marketdata.models import Bar\n")),
    ("celery in package", write("packages/sd_models/x.py", "from celery import shared_task\n")),
    ("django in fm_worker", write("apps/fm_worker/sd_fm/tasks.py", "from django.conf import settings\n")),
    ("NEXT_PUBLIC secret", write("apps/web/lib/api.ts", "const k = process.env.NEXT_PUBLIC_ANTHROPIC_KEY\n")),
    ("anthropic sdk in browser", write("apps/web/components/advisor/x.ts", "import Anthropic from '@anthropic-ai/sdk'\n")),
    (".env write", write(".env", "SECRET_KEY=x\n")),
    (".env.local write", write(".env.local", "X=1\n")),
    ("generated contracts", write("apps/web/lib/contracts/ws.ts", "export type X = 1\n")),
    ("api key in docs", write("docs/reports/x.md", f"key: {FAKE_KEY}\n")),
]

ALLOWED_WRITES = [
    ("order token in docs", write("docs/plans/F2-mt5-gateway.md", f"Never call {ORDER}.\n")),
    ("order token in rules", write(".claude/rules/mt5-gateway.md", f"No {ORDER}.\n")),
    ("order token in CLAUDE.md", write("CLAUDE.md", f"Never use {ORDER}.\n")),
    ("order token in structural tests", write("tests/structural/test_no_order_code.py", f"PATTERN = '{ORDER}'\n")),
    ("MetaTrader5 in gateway client", write("apps/gateway/sd_gateway/mt5_client.py", "import MetaTrader5 as mt5\n")),
    ("MetaTrader5 in spike", write("apps/gateway/spike/spike.py", "import MetaTrader5 as mt5\n")),
    ("advisor client in advisor views", write("apps/backend/advisor/views.py", "from sd_advisor.client import AnthropicAdvisorClient\n")),
    ("anthropic in sd_advisor package", write("packages/sd_advisor/client.py", "import anthropic\n")),
    ("advisor tests", write("apps/backend/advisor/tests/test_ask.py", "from sd_advisor.client import FakeAdvisorClient\n")),
    ("sd_advisor packet in advisor services", write("apps/backend/advisor/services.py", "from sd_advisor.packet import build_packet\n")),
    ("celery in fm_worker", write("apps/fm_worker/sd_fm/tasks.py", "from celery import shared_task\n")),
    ("django in backend", write("apps/backend/marketdata/models.py", "from django.db import models\n")),
    ("sd_core in package", write("packages/sd_features/indicators.py", "from sd_core.time import to_utc\n")),
    ("relative config import in package", write("packages/sd_advisor/request.py", "from .config import AdvisorConfig\n")),
    ("non-secret NEXT_PUBLIC", write("apps/web/lib/env.ts", "process.env.NEXT_PUBLIC_APP_NAME\n")),
    (".env.example", write(".env.example", "ANTHROPIC_API_KEY=\n")),
    ("outside repo", {"tool_name": "Write", "tool_input": {"file_path": "Z:\\elsewhere\\x.py", "content": f"mt5.{ORDER}()"}}),
]

BLOCKED_COMMANDS = [
    ("echo order code to file", command(f'echo "mt5.{ORDER}(r)" > apps/backend/x.py')),
    ("heredoc anthropic import", command("cat > apps/backend/signals/x.py <<'EOF'\nimport anthropic\nEOF")),
    ("PowerShell Set-Content import", command("Set-Content -Path x.py -Value 'import anthropic'", "PowerShell")),
    ("write .env", command("echo SECRET=1 > .env")),
    ("write contracts", command("echo x > apps/web/lib/contracts/ws.ts")),
]

ALLOWED_COMMANDS = [
    ("grep for the token", command(f"grep -rn {ORDER} .")),
    ("rg with stderr redirect", command(f"rg {ORDER} apps 2>&1")),
    ("git commit mentioning the ban", command(f"git commit -m \"$(cat <<'EOF'\ntest: assert no {ORDER}\nEOF\n)\"")),
    ("write .env.example", command("echo ANTHROPIC_API_KEY= > .env.example")),
    ("plain test run", command("python -m pytest tests -q")),
    ("redirect to dev null", command("python manage.py check > /dev/null")),
]


class GuardTests(unittest.TestCase):
    def test_blocked_writes(self) -> None:
        for name, payload in BLOCKED_WRITES:
            with self.subTest(name):
                res = run_guard(payload)
                self.assertEqual(res.returncode, 2, f"{name}: expected block, stderr={res.stderr!r}")
                self.assertIn("Blocked by", res.stderr)

    def test_allowed_writes(self) -> None:
        for name, payload in ALLOWED_WRITES:
            with self.subTest(name):
                res = run_guard(payload)
                self.assertEqual(res.returncode, 0, f"{name}: expected allow, stderr={res.stderr!r}")

    def test_blocked_commands(self) -> None:
        for name, payload in BLOCKED_COMMANDS:
            with self.subTest(name):
                res = run_guard(payload, "--command")
                self.assertEqual(res.returncode, 2, f"{name}: expected block, stderr={res.stderr!r}")

    def test_allowed_commands(self) -> None:
        for name, payload in ALLOWED_COMMANDS:
            with self.subTest(name):
                res = run_guard(payload, "--command")
                self.assertEqual(res.returncode, 0, f"{name}: expected allow, stderr={res.stderr!r}")

    def test_lowercase_drive_and_forward_slashes(self) -> None:
        p = str(ROOT / "apps/backend/marketdata/api.py").replace("\\", "/")
        p = p[0].lower() + p[1:]
        res = run_guard({"tool_name": "Write", "tool_input": {"file_path": p, "content": "import MetaTrader5\n"}})
        self.assertEqual(res.returncode, 2, res.stderr)

    def test_malformed_input_is_non_blocking(self) -> None:
        self.assertEqual(run_guard("not json").returncode, 1)


class BranchProtectionTests(unittest.TestCase):
    """`git commit` is blocked on main/development; work goes through wp/ or chore/ branches."""

    COMMIT_FORMS = [
        "git commit -m 'feat(P0-WP01): x'",
        "git add -A && git commit -m \"msg\"",
        "git commit --amend --no-edit",
        "git -C . commit -m x",
        "git -c user.name=x commit -m x",
        "git add . ; git commit -m x",
    ]
    NOT_COMMITS = [
        "git merge --no-ff wp/P0-WP01-x -m \"merge(P0-WP01): commit the work\"",
        "git log --oneline",
        "git status",
        "git switch -c chore/x",
        "git push -u origin development",
        "echo done",
    ]

    def test_commit_blocked_on_protected_branches(self) -> None:
        for branch in ("main", "development"):
            for cmd in self.COMMIT_FORMS:
                with self.subTest(branch=branch, cmd=cmd):
                    res = run_guard(command(cmd), "--command", branch=branch)
                    self.assertEqual(res.returncode, 2, res.stderr)
                    self.assertIn("is blocked", res.stderr)

    def test_commit_allowed_on_work_branches(self) -> None:
        for branch in ("wp/P1-WP02-ingest-streams", "chore/development-workflow", "feature/x"):
            for cmd in self.COMMIT_FORMS:
                with self.subTest(branch=branch, cmd=cmd):
                    self.assertEqual(run_guard(command(cmd), "--command", branch=branch).returncode, 0)

    def test_commit_allowed_while_concluding_a_merge(self) -> None:
        res = run_guard(command("git commit --no-edit"), "--command", branch="development", merging=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_other_git_commands_never_blocked(self) -> None:
        for branch in ("main", "development"):
            for cmd in self.NOT_COMMITS:
                with self.subTest(branch=branch, cmd=cmd):
                    self.assertEqual(run_guard(command(cmd), "--command", branch=branch).returncode, 0)

    def test_powershell_commit_blocked(self) -> None:
        res = run_guard(command("git commit -m 'x'", "PowerShell"), "--command", branch="development")
        self.assertEqual(res.returncode, 2, res.stderr)


class PrePushHookTests(unittest.TestCase):
    def test_hook_exists_and_has_valid_shell_syntax(self) -> None:
        self.assertTrue(PRE_PUSH.exists(), ".githooks/pre-push is missing")
        sh = shutil.which("sh")
        if sh is None:
            self.skipTest("sh not available")
        res = subprocess.run([sh, "-n", str(PRE_PUSH)], capture_output=True, text=True, timeout=10)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_hook_runs_the_local_gate_and_forbids_bypass(self) -> None:
        text = PRE_PUSH.read_text(encoding="utf-8")
        self.assertIn("just check", text)
        self.assertIn("unittest discover -s tests/structural", text)
        self.assertIn("exit 1", text)  # a failing gate must block the push


class SessionContextTests(unittest.TestCase):
    def test_prints_phase_and_branch(self) -> None:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)}
        res = subprocess.run([sys.executable, str(SESSION)], capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Current phase:", res.stdout)
        self.assertIn("Git branch:", res.stdout)


if __name__ == "__main__":
    unittest.main()
