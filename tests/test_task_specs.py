from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from agent_dev_swarm.task_specs import load_task_spec


class TaskSpecTests(unittest.TestCase):
    def make_project(self, task_name: str = "issue-3.yaml", task_yaml: str | None = None) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
        if task_yaml is not None:
            task_dir = project_root / ".swarm" / "tasks"
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / task_name).write_text(
                textwrap.dedent(task_yaml).strip() + "\n",
                encoding="utf-8",
            )
        return project_root

    def run_cli(self, project_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_dev_swarm.cli",
                "load-task-spec",
                "--project",
                str(project_root),
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def valid_task_yaml(self) -> str:
        return """
        task_id: issue-3
        title: Add task-spec loading contract
        goal: Load and validate one bounded task spec.
        scope:
          - Add the task-spec loader.
          - Add CLI text and JSON output.
        non_goals:
          - Do not execute the task.
        required_outputs:
          - Structured result object.
          - Terminal summary.
        success_criteria:
          - A valid task spec loads successfully.
          - Invalid task specs fail with explicit reasons.
        notes: Keep the schema small and inspectable.
        allowed_roots:
          - src
          - tests
        suggested_commands:
          - python -m unittest discover -s tests -v
        verification_commands:
          - python -m unittest discover -s tests -v
        implementation_record_path: .swarm/implementation-records/issue-3-load-task-spec.md
        """

    def test_load_task_spec_success_with_task_id_resolution(self) -> None:
        project_root = self.make_project(task_yaml=self.valid_task_yaml())

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.task_id, "issue-3")
        self.assertIsNotNone(result.parsed_task)
        assert result.parsed_task is not None
        self.assertEqual(result.parsed_task.title, "Add task-spec loading contract")
        self.assertEqual(result.parsed_task.allowed_roots, ["src", "tests"])
        self.assertEqual(result.parsed_task.verification_commands, ["python -m unittest discover -s tests -v"])

    def test_load_task_spec_success_with_explicit_relative_path(self) -> None:
        project_root = self.make_project(task_name="custom.yaml", task_yaml=self.valid_task_yaml())
        target_path = project_root / ".swarm" / "tasks" / "custom.yaml"

        result = load_task_spec(project_root, ".swarm/tasks/custom.yaml")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.task_path, target_path.resolve())

    def test_load_task_spec_fails_when_task_file_missing(self) -> None:
        project_root = self.make_project()

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing task spec file", result.errors[0])

    def test_load_task_spec_fails_when_yaml_invalid(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            task_id: issue-3
            title: [broken
            """
        )

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "failure")
        self.assertIn("Failed to parse task spec YAML", result.errors[0])

    def test_load_task_spec_fails_when_top_level_yaml_is_not_mapping(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            - task_id: issue-3
            - title: bad shape
            """
        )

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "failure")
        self.assertIn("Expected YAML mapping", result.errors[0])

    def test_load_task_spec_fails_when_required_field_missing(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            task_id: issue-3
            title: Add task-spec loading contract
            goal: Load and validate one bounded task spec.
            scope:
              - Add the task-spec loader.
            non_goals:
              - Do not execute the task.
            required_outputs:
              - Structured result object.
            """
        )

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing required task fields: success_criteria", result.errors[0])

    def test_load_task_spec_fails_when_required_string_field_empty(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            task_id: issue-3
            title: ""
            goal: Load and validate one bounded task spec.
            scope:
              - Add the task-spec loader.
            non_goals:
              - Do not execute the task.
            required_outputs:
              - Structured result object.
            success_criteria:
              - A valid task spec loads successfully.
            """
        )

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "failure")
        self.assertIn("Field 'title' must be a non-empty string.", result.errors[0])

    def test_load_task_spec_fails_when_required_list_field_empty(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            task_id: issue-3
            title: Add task-spec loading contract
            goal: Load and validate one bounded task spec.
            scope: []
            non_goals:
              - Do not execute the task.
            required_outputs:
              - Structured result object.
            success_criteria:
              - A valid task spec loads successfully.
            """
        )

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "failure")
        self.assertIn("Field 'scope' must be a non-empty list of non-empty strings.", result.errors[0])

    def test_load_task_spec_fails_when_required_list_contains_invalid_entry(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            task_id: issue-3
            title: Add task-spec loading contract
            goal: Load and validate one bounded task spec.
            scope:
              - Add the task-spec loader.
              - ""
            non_goals:
              - Do not execute the task.
            required_outputs:
              - Structured result object.
            success_criteria:
              - A valid task spec loads successfully.
            """
        )

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "failure")
        self.assertIn("Field 'scope' contains an invalid entry at index 1", result.errors[0])

    def test_load_task_spec_fails_when_optional_field_invalid(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            task_id: issue-3
            title: Add task-spec loading contract
            goal: Load and validate one bounded task spec.
            scope:
              - Add the task-spec loader.
            non_goals:
              - Do not execute the task.
            required_outputs:
              - Structured result object.
            success_criteria:
              - A valid task spec loads successfully.
            verification_commands:
              - python -m unittest discover -s tests -v
              - 123
            """
        )

        result = load_task_spec(project_root, "issue-3")

        self.assertEqual(result.status, "failure")
        self.assertIn("Field 'verification_commands' contains an invalid entry at index 1", result.errors[0])

    def test_cli_load_task_spec_text_success(self) -> None:
        project_root = self.make_project(task_yaml=self.valid_task_yaml())

        completed = self.run_cli(project_root, "--task", "issue-3")

        self.assertEqual(completed.returncode, 0)
        self.assertIn("load-task-spec: SUCCESS", completed.stdout)
        self.assertIn("summary: task spec is valid and ready for bounded handoff.", completed.stdout)

    def test_cli_load_task_spec_json_success(self) -> None:
        project_root = self.make_project(task_yaml=self.valid_task_yaml())

        completed = self.run_cli(project_root, "--task", "issue-3", "--format", "json")

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["task_id"], "issue-3")
        self.assertEqual(payload["parsed_task"]["title"], "Add task-spec loading contract")

    def test_cli_load_task_spec_json_failure_for_invalid_task(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            task_id: issue-3
            title: Add task-spec loading contract
            goal: Load and validate one bounded task spec.
            scope: []
            non_goals:
              - Do not execute the task.
            required_outputs:
              - Structured result object.
            success_criteria:
              - A valid task spec loads successfully.
            """
        )

        completed = self.run_cli(project_root, "--task", "issue-3", "--format", "json")

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failure")
        self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()