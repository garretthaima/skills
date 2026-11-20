"""Tests for the read-only agent Bash guard. Run: python3 -m unittest discover tests"""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "plugins/flow/scripts/readonly_agent_bash.py"
spec = importlib.util.spec_from_file_location("readonly_agent_bash", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

ALLOWED = [
    "git diff main...HEAD",
    "git -C /work/tree log --oneline -5",
    "git --no-pager show HEAD:README.md",
    "git status 2>&1",
    "git branch --show-current",
    "git branch -a --contains abc123",
    "git tag --list 'v*'",
    "git remote -v",
    "git remote get-url origin",
    "git worktree list",
    "git grep -n needle -- src",
    "gh pr view 12 --json files",
    "gh pr diff 12",
    "gh issue list --state open",
    "gh search issues needle",
    "gh api repos/o/r/contents/README.md",
    "gh api -X GET repos/o/r/pulls",
    "git log -1 && gh pr checks 12",
    "git diff --stat | git grep x",
]

DENIED = [
    "",
    "ls",
    "cat README.md",
    "git push",
    "git commit -m x",
    "git checkout main",
    "git stash",
    "git -c core.pager=sh log",
    "git branch new-branch",
    "git branch -D old",
    "git tag v1",
    "git remote add x y",
    "git remote -v set-url origin y",
    "git worktree add ../x",
    "git diff --output=/tmp/x",
    "git grep -Osh needle",
    "git log > out.txt",
    "git log $(whoami)",
    "git log `whoami`",
    "git log & echo hi",
    "git log; rm -rf x",
    "git log && npm test",
    "gh auth status --show-token",
    "gh pr merge 12",
    "gh pr create",
    "gh issue close 3",
    "gh api -X POST repos/o/r/issues",
    "gh api --method=DELETE repos/o/r",
    "gh api repos/o/r/issues -f title=x",
    "gh api repos/o/r/issues -ftitle=x",
    "git log 'unterminated",
]


def run_hook(payload):
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)],
        input=json.dumps(payload) if payload is not None else "not json",
        capture_output=True, text=True, timeout=10,
    )
    return proc.returncode, proc.stdout


def bash(command, agent_type=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent_type is not None:
        payload["agent_type"] = agent_type
    return payload


class DecideTest(unittest.TestCase):
    def test_read_only_commands_are_allowed(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(guard.decide(command))

    def test_everything_else_is_denied(self):
        for command in DENIED:
            with self.subTest(command=command):
                self.assertIsNotNone(guard.decide(command))


class AgentScopeTest(unittest.TestCase):
    def test_only_this_plugins_read_only_agents_are_guarded(self):
        for agent_type in ("flow:code-reviewer", "flow:epic-verifier", "flow:docs-auditor"):
            self.assertTrue(guard.is_read_only_agent(agent_type), agent_type)
        for agent_type in (None, "", "code-reviewer", "flow:issue-owner", "Explore",
                           "other-plugin:code-reviewer", 7):
            self.assertFalse(guard.is_read_only_agent(agent_type), agent_type)


class HookTest(unittest.TestCase):
    def test_denies_a_write_inside_a_read_only_agent(self):
        code, out = run_hook(bash("git push", "flow:code-reviewer"))
        self.assertEqual(code, 0)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Read-only agent", decision["permissionDecisionReason"])

    def test_allows_a_read_inside_a_read_only_agent(self):
        self.assertEqual(run_hook(bash("git diff main...HEAD", "flow:code-reviewer")), (0, ""))

    def test_stays_out_of_the_way_everywhere_else(self):
        for payload in (
            bash("rm -rf build"),
            bash("npm test", "flow:issue-owner"),
            bash("git push", "other-plugin:code-reviewer"),
            {"tool_name": "Edit", "agent_type": "flow:code-reviewer"},
            None,
        ):
            with self.subTest(payload=payload):
                self.assertEqual(run_hook(payload), (0, ""))

    def test_fails_closed_on_a_malformed_command_in_a_read_only_agent(self):
        payload = {"tool_name": "Bash", "tool_input": "oops", "agent_type": "flow:docs-auditor"}
        code, out = run_hook(payload)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
