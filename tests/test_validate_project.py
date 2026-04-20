from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from agent_dev_swarm.validate_project import validate_project


class ValidateProjectTests(unittest.TestCase):
    def make_project(self, project_yaml: str | None = None) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
        if project_yaml is not None:
            config_dir = project_root / ".swarm"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "project.yaml").write_text(
                textwrap.dedent(project_yaml).strip() + "\n",
                encoding="utf-8",
            )
        return project_root

    def run_cli(self, project_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_dev_swarm.cli",
                "validate-project",
                "--project",
                str(project_root),
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_validate_project_success(self) -> None:
        project_root = self.make_project(
            """
            project_name: demo-project
            framework_checkout: swarm
            rules_doc: docs/rules.md
            artifact_spec_doc: docs/artifact-spec.md
            """
        )
        (project_root / "swarm").mkdir()
        docs_dir = project_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "rules.md").write_text("rules\n", encoding="utf-8")
        (docs_dir / "artifact-spec.md").write_text("spec\n", encoding="utf-8")

        result = validate_project(project_root)

        self.assertEqual(result.status, "success")
        self.assertFalse(result.errors)

    def test_validate_project_fails_when_config_missing(self) -> None:
        project_root = self.make_project()

        result = validate_project(project_root)

        self.assertEqual(result.status, "failure")
        self.assertIn("Project config file .swarm/project.yaml was not found.", result.errors)

    def test_validate_project_fails_when_required_field_missing(self) -> None:
        project_root = self.make_project(
            """
            project_name: demo-project
            """
        )

        result = validate_project(project_root)

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing required YAML fields: framework_checkout", result.errors)

    def test_validate_project_fails_when_framework_checkout_missing(self) -> None:
        project_root = self.make_project(
            """
            project_name: demo-project
            framework_checkout: swarm
            """
        )

        result = validate_project(project_root)

        self.assertEqual(result.status, "failure")
        self.assertIn("Configured framework checkout does not exist", result.errors[0])

    def test_validate_project_fails_when_referenced_doc_missing(self) -> None:
        project_root = self.make_project(
            """
            project_name: demo-project
            framework_checkout: swarm
            bootstrap_plan_doc: docs/bootstrap-plan.md
            """
        )
        (project_root / "swarm").mkdir()

        result = validate_project(project_root)

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing referenced docs:", result.errors[0])

    def test_cli_validate_project_default_text_success(self) -> None:
        project_root = self.make_project(
            """
            project_name: demo-project
            framework_checkout: swarm
            """
        )
        (project_root / "swarm").mkdir()

        completed = self.run_cli(project_root)

        self.assertEqual(completed.returncode, 0)
        self.assertIn("validate-project: SUCCESS", completed.stdout)

    def test_cli_validate_project_explicit_text_success(self) -> None:
        project_root = self.make_project(
            """
            project_name: demo-project
            framework_checkout: swarm
            """
        )
        (project_root / "swarm").mkdir()

        completed = self.run_cli(project_root, "--format", "text")

        self.assertEqual(completed.returncode, 0)
        self.assertIn("validate-project: SUCCESS", completed.stdout)
        self.assertIn("summary: project attachment is valid.", completed.stdout)

    def test_cli_validate_project_json_success(self) -> None:
        project_root = self.make_project(
            """
            project_name: demo-project
            framework_checkout: swarm
            rules_doc: docs/rules.md
            """
        )
        (project_root / "swarm").mkdir()
        docs_dir = project_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "rules.md").write_text("rules\n", encoding="utf-8")

        completed = self.run_cli(project_root, "--format", "json")

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["project_root"], str(project_root.resolve()))
        self.assertIn("config_path", payload)
        self.assertIn("checks", payload)
        self.assertIn("missing_items", payload)
        self.assertIn("errors", payload)
        self.assertTrue(any(check["name"] == "project_config_exists" for check in payload["checks"]))

    def test_cli_validate_project_json_failure(self) -> None:
        project_root = self.make_project()

        completed = self.run_cli(project_root, "--format", "json")

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failure")
        self.assertTrue(payload["errors"])
        self.assertTrue(any(check["status"] == "fail" for check in payload["checks"]))
        self.assertIn(str((project_root / ".swarm" / "project.yaml").resolve()), payload["missing_items"])


if __name__ == "__main__":
    unittest.main()