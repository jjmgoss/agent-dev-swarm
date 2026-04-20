from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from agent_dev_swarm.execution_policy import check_command_policy, load_execution_policy


class ExecutionPolicyTests(unittest.TestCase):
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

    def run_cli(self, project_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_dev_swarm.cli",
                "check-command-policy",
                "--project",
                str(project_root),
                "--policy",
                ".swarm/execution-policy.yaml",
                "--cwd",
                ".",
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_load_execution_policy_success(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - .
              - tests/fixtures
            allowed_command_prefixes:
              - python -m unittest
              - git status
            blocked_command_patterns:
              - git reset --hard
            timeout_seconds: 120
            max_output_bytes: 200000
            allow_network: false
            allow_package_install: false
            allow_git_write: false
            """
        )

        policy = load_execution_policy(project_root, Path(".swarm/execution-policy.yaml"))

        self.assertEqual(policy.allowed_command_prefixes[0], "python -m unittest")
        self.assertEqual(policy.allowed_roots[0], project_root.resolve())
        self.assertFalse(policy.allow_network)

    def test_check_command_policy_allows_command(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - .
            allowed_command_prefixes:
              - python -m unittest
            blocked_command_patterns:
              - git reset --hard
            """
        )

        result = check_command_policy(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=["python", "-m", "unittest", "discover", "-s", "tests"],
        )

        self.assertEqual(result.status, "allowed")
        self.assertFalse(result.errors)
        self.assertEqual(result.matched_allowed_prefix, "python -m unittest")

    def test_check_command_policy_refuses_missing_policy_file(self) -> None:
        project_root = self.make_project()

        result = check_command_policy(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=["python", "-m", "unittest"],
        )

        self.assertEqual(result.status, "refused")
        self.assertIn("Missing execution policy file", result.errors[0])

    def test_check_command_policy_refuses_invalid_yaml(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - .
            allowed_command_prefixes: [python -m unittest
            """
        )

        result = check_command_policy(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=["python", "-m", "unittest"],
        )

        self.assertEqual(result.status, "refused")
        self.assertIn("Failed to parse execution policy YAML", result.errors[0])

    def test_check_command_policy_refuses_cwd_outside_allowed_roots(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - src
            allowed_command_prefixes:
              - python -m unittest
            """
        )

        result = check_command_policy(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("docs"),
            command=["python", "-m", "unittest"],
        )

        self.assertEqual(result.status, "refused")
        self.assertTrue(any(check.name == "cwd_within_allowed_roots" and check.status == "fail" for check in result.checks))

    def test_check_command_policy_refuses_command_not_on_allowlist(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - .
            allowed_command_prefixes:
              - python -m unittest
            """
        )

        result = check_command_policy(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=["git", "status"],
        )

        self.assertEqual(result.status, "refused")
        self.assertTrue(any(check.name == "command_matches_allowed_prefix" and check.status == "fail" for check in result.checks))

    def test_check_command_policy_refuses_blocked_pattern(self) -> None:
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

        result = check_command_policy(
            project_root=project_root,
            policy_path=Path(".swarm/execution-policy.yaml"),
            cwd=Path("."),
            command=["git", "reset", "--hard", "HEAD"],
        )

        self.assertEqual(result.status, "refused")
        self.assertEqual(result.matched_allowed_prefix, "git")
        self.assertEqual(result.matched_blocked_pattern, "git reset --hard")

    def test_cli_check_command_policy_text_success(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - .
            allowed_command_prefixes:
              - python -m unittest
            """
        )

        completed = self.run_cli(project_root, "--", "python", "-m", "unittest")

        self.assertEqual(completed.returncode, 0)
        self.assertIn("check-command-policy: ALLOWED", completed.stdout)

    def test_cli_check_command_policy_json_failure(self) -> None:
        project_root = self.make_project(
            """
            allowed_roots:
              - src
            allowed_command_prefixes:
              - python -m unittest
            blocked_command_patterns:
              - git reset --hard
            """
        )

        completed = self.run_cli(
            project_root,
            "--format",
            "json",
            "--cwd",
            "docs",
            "--",
            "git",
            "reset",
            "--hard",
            "HEAD",
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "refused")
        self.assertTrue(payload["errors"])
        self.assertTrue(any(check["status"] == "fail" for check in payload["checks"]))
        self.assertEqual(payload["matched_blocked_pattern"], "git reset --hard")


if __name__ == "__main__":
    unittest.main()