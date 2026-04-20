from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from agent_dev_swarm.execution_policy import run_checked_command


class RunCheckedCommandTests(unittest.TestCase):
    def make_project(self, policy_yaml: str | None = None) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
        if policy_yaml is not None:
            policy_dir = project_root / ".swarm"
            policy_dir.mkdir(parents=True, exist_ok=True)
            (policy_dir / "execution-policy.yaml").write_text(
                textwrap.dedent(policy_yaml).strip() + "\n",
                encoding="utf-8",
            )
        return project_root

    def run_cli(self, project_root: Path, cwd: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_dev_swarm.cli",
                "run-checked-command",
                "--project",
                str(project_root),
                "--policy",
                ".swarm/execution-policy.yaml",
                "--cwd",
                cwd,
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_run_checked_command_success(self) -> None:
        project_root = self.make_project(
            f"""
            allowed_roots:
              - .
            allowed_command_prefixes:
              - {sys.executable} -c
            """
        )

        result = run_checked_command(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=[sys.executable, "-c", "print('hello from checked command')"],
        )

        self.assertEqual(result.status, "success")
        self.assertTrue(result.execution_performed)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello from checked command", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_run_checked_command_refuses_missing_policy_file(self) -> None:
        project_root = self.make_project()

        result = run_checked_command(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=[sys.executable, "-c", "print('hello')"],
        )

        self.assertEqual(result.status, "refused")
        self.assertFalse(result.execution_performed)
        self.assertIn("Missing execution policy file", result.errors[0])

    def test_run_checked_command_refuses_invalid_yaml(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - .
            allowed_command_prefixes: [python -c
            """
        )

        result = run_checked_command(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=[sys.executable, "-c", "print('hello')"],
        )

        self.assertEqual(result.status, "refused")
        self.assertFalse(result.execution_performed)
        self.assertIn("Failed to parse execution policy YAML", result.errors[0])

    def test_run_checked_command_refuses_cwd_outside_allowed_roots(self) -> None:
        project_root = self.make_project(
            f"""
            allowed_roots:
              - src
            allowed_command_prefixes:
              - {sys.executable} -c
            """
        )

        result = run_checked_command(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("docs"),
            command=[sys.executable, "-c", "print('hello')"],
        )

        self.assertEqual(result.status, "refused")
        self.assertFalse(result.execution_performed)
        self.assertTrue(any(check.name == "cwd_within_allowed_roots" and check.status == "fail" for check in result.checks))

    def test_run_checked_command_refuses_command_not_on_allowlist(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - .
            allowed_command_prefixes:
              - python -m unittest
            """
        )

        result = run_checked_command(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=["git", "status"],
        )

        self.assertEqual(result.status, "refused")
        self.assertFalse(result.execution_performed)
        self.assertTrue(any(check.name == "command_matches_allowed_prefix" and check.status == "fail" for check in result.checks))

    def test_run_checked_command_refuses_blocked_pattern(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - .
            allowed_command_prefixes:
              - git
            blocked_command_patterns:
              - git reset --hard
            """
        )

        result = run_checked_command(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=["git", "reset", "--hard", "HEAD"],
        )

        self.assertEqual(result.status, "refused")
        self.assertFalse(result.execution_performed)
        self.assertEqual(result.matched_blocked_pattern, "git reset --hard")

    def test_run_checked_command_failure_captures_output(self) -> None:
        project_root = self.make_project(
            f"""
            allowed_roots:
              - .
            allowed_command_prefixes:
              - {sys.executable} -c
            """
        )

        result = run_checked_command(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=[
                sys.executable,
                "-c",
                "import sys; print('before fail'); print('boom', file=sys.stderr); raise SystemExit(3)",
            ],
        )

        self.assertEqual(result.status, "failure")
        self.assertTrue(result.execution_performed)
        self.assertEqual(result.exit_code, 3)
        self.assertIn("before fail", result.stdout)
        self.assertIn("boom", result.stderr)

    def test_run_checked_command_timeout(self) -> None:
        project_root = self.make_project(
            f"""
            allowed_roots:
              - .
            allowed_command_prefixes:
              - {sys.executable} -c
            timeout_seconds: 1
            """
        )

        result = run_checked_command(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=[sys.executable, "-c", "import time; print('start'); time.sleep(2)"],
        )

        self.assertEqual(result.status, "timeout")
        self.assertTrue(result.execution_performed)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertIn("Command exceeded timeout of 1 seconds.", result.errors)

    def test_cli_run_checked_command_text_success(self) -> None:
        project_root = self.make_project(
            f"""
            allowed_roots:
              - .
            allowed_command_prefixes:
              - {sys.executable} -c
            """
        )

        completed = self.run_cli(
            project_root,
            ".",
            "--",
            sys.executable,
            "-c",
            "print('cli success')",
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("run-checked-command: SUCCESS", completed.stdout)
        self.assertIn("cli success", completed.stdout)

    def test_cli_run_checked_command_json_refusal(self) -> None:
        project_root = self.make_project(
            f"""
            allowed_roots:
              - src
            allowed_command_prefixes:
              - {sys.executable} -c
            blocked_command_patterns:
              - git reset --hard
            """
        )

        completed = self.run_cli(
            project_root,
            "docs",
            "--format",
            "json",
            "--",
            "git",
            "reset",
            "--hard",
            "HEAD",
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "refused")
        self.assertFalse(payload["execution_performed"])
        self.assertTrue(payload["errors"])

    def test_cli_run_checked_command_json_failure_uses_child_exit_code(self) -> None:
        project_root = self.make_project(
            f"""
            allowed_roots:
              - .
            allowed_command_prefixes:
              - {sys.executable} -c
            """
        )

        completed = self.run_cli(
            project_root,
            ".",
            "--format",
            "json",
            "--",
            sys.executable,
            "-c",
            "import sys; print('fail path'); raise SystemExit(5)",
        )

        self.assertEqual(completed.returncode, 5)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failure")
        self.assertTrue(payload["execution_performed"])
        self.assertEqual(payload["exit_code"], 5)
        self.assertIn("fail path", payload["stdout"])


if __name__ == "__main__":
    unittest.main()