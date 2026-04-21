from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from uuid import uuid4

from agent_dev_swarm.sandbox_fixtures import materialize_sandbox_run
from agent_dev_swarm.supervised_runs import scaffold_supervised_run


class SupervisedRunTests(unittest.TestCase):
    def make_fixture(
        self,
        fixtures_root: Path,
        fixture_name: str = "tiny-supervised",
        manifest_yaml: str | None = None,
        task_yaml: str | None = None,
    ) -> Path:
        fixture_root = fixtures_root / fixture_name
        source_root = fixture_root / "project"
        (source_root / "src").mkdir(parents=True, exist_ok=True)
        (source_root / ".swarm" / "tasks").mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("fixture\n", encoding="utf-8")
        (source_root / "src" / "tool.py").write_text("VALUE = 1\n", encoding="utf-8")
        (source_root / ".swarm" / "tasks" / "issue-1.yaml").write_text(
            textwrap.dedent(
                task_yaml
                or """
                task_id: issue-1
                title: Tiny supervised run fixture
                goal: Validate supervised run scaffolding.
                scope:
                  - Build the worker handoff artifact.
                  - Create a worker-result starter.
                non_goals:
                  - Do not execute the task.
                required_outputs:
                  - Worker handoff artifact.
                  - Worker-result starter artifact.
                success_criteria:
                  - The handoff artifact exists.
                  - The starter payload exists.
                implementation_record_path: .swarm/implementation-records/issue-1.md
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (source_root / ".swarm" / "execution-policy.yaml").write_text(
            "allowed_roots:\n"
            "  - .\n"
            "allowed_command_prefixes:\n"
            "  - python -m unittest\n",
            encoding="utf-8",
        )
        (fixture_root / "fixture.yaml").write_text(
            textwrap.dedent(
                manifest_yaml
                or """
                fixture_id: tiny-supervised
                description: Small supervised-run test fixture.
                layout_version: "1"
                source_root: project
                materialized_paths:
                  - README.md
                  - src
                  - .swarm/tasks
                  - .swarm/execution-policy.yaml
                editable_paths:
                  - src
                read_only_paths:
                  - README.md
                  - .swarm/tasks
                  - .swarm/execution-policy.yaml
                generated_paths:
                  - .swarm/evidence
                  - .swarm/results
                  - .swarm/implementation-records
                default_task_spec: .swarm/tasks/issue-1.yaml
                default_policy: .swarm/execution-policy.yaml
                intended_outcome: accept
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return fixture_root

    def make_roots(self) -> tuple[Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        temp_root = Path(temp_dir.name)
        fixtures_root = temp_root / "fixtures"
        runs_root = temp_root / "runs"
        fixtures_root.mkdir(parents=True, exist_ok=True)
        runs_root.mkdir(parents=True, exist_ok=True)
        return fixtures_root, runs_root

    def materialize_run(self, fixtures_root: Path, runs_root: Path, run_id: str) -> Path:
        self.make_fixture(fixtures_root)
        result = materialize_sandbox_run(
            fixture_name="tiny-supervised",
            run_id=run_id,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )
        self.assertEqual(result.status, "success")
        return runs_root / run_id

    def materialize_existing_run(self, fixtures_root: Path, runs_root: Path, run_id: str) -> Path:
        result = materialize_sandbox_run(
            fixture_name="tiny-supervised",
            run_id=run_id,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )
        self.assertEqual(result.status, "success")
        return runs_root / run_id

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "agent_dev_swarm.cli", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_scaffold_supervised_run_success(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        run_root = self.materialize_run(fixtures_root, runs_root, "run-1")

        result = scaffold_supervised_run(
            run_id="run-1",
            worker_role="implementation-worker",
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.task_source, "manifest_default")
        self.assertEqual(result.policy_source, "manifest_default")
        self.assertTrue((run_root / "artifacts" / "handoff" / "worker-handoff.json").is_file())
        self.assertTrue((run_root / "artifacts" / "worker-result" / "worker-result-starter.json").is_file())
        self.assertTrue((run_root / "artifacts" / "summary" / "run-plan.json").is_file())

        starter = json.loads(
            (run_root / "artifacts" / "worker-result" / "worker-result-starter.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(starter["task_id"], "issue-1")
        self.assertEqual(starter["worker_role"], "implementation-worker")
        self.assertEqual(starter["verification_status"], "not_run")
        self.assertEqual(starter["status"], "partial")
        self.assertEqual(starter["required_outputs_status"][0]["name"], "Worker handoff artifact.")
        self.assertEqual(starter["required_outputs_status"][0]["status"], "not_evaluated")
        self.assertEqual(starter["success_criteria_status"][0]["status"], "not_evaluated")

    def test_scaffold_supervised_run_fails_when_run_missing(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)

        result = scaffold_supervised_run(
            run_id="missing-run",
            worker_role="implementation-worker",
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing sandbox run directory", result.errors[0])

    def test_scaffold_supervised_run_fails_when_run_metadata_missing(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        run_root = self.materialize_run(fixtures_root, runs_root, "run-1")
        (run_root / "run-info.json").unlink()

        result = scaffold_supervised_run(
            run_id="run-1",
            worker_role="implementation-worker",
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing sandbox run metadata file", result.errors[0])

    def test_scaffold_supervised_run_fails_when_default_task_missing(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        run_root = self.materialize_run(fixtures_root, runs_root, "run-1")
        (run_root / "workspace" / ".swarm" / "tasks" / "issue-1.yaml").unlink()

        result = scaffold_supervised_run(
            run_id="run-1",
            worker_role="implementation-worker",
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing default task spec file", result.errors[0])

    def test_scaffold_supervised_run_fails_when_task_invalid(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        self.make_fixture(
            fixtures_root,
            task_yaml="""
            task_id: issue-1
            title: Broken supervised run fixture
            goal: Broken task.
            scope: []
            non_goals:
              - Do not execute the task.
            required_outputs:
              - Worker handoff artifact.
            success_criteria:
              - The handoff artifact exists.
            """,
        )
        self.materialize_existing_run(fixtures_root, runs_root, "run-1")

        result = scaffold_supervised_run(
            run_id="run-1",
            worker_role="implementation-worker",
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "failure")
        self.assertTrue(any("Field 'scope' must be a non-empty list of non-empty strings." in error for error in result.errors))

    def test_scaffold_supervised_run_refuses_existing_artifacts_without_overwrite(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        self.materialize_run(fixtures_root, runs_root, "run-1")

        first = scaffold_supervised_run(
            run_id="run-1",
            worker_role="implementation-worker",
            runs_root=runs_root,
        )
        second = scaffold_supervised_run(
            run_id="run-1",
            worker_role="implementation-worker",
            runs_root=runs_root,
        )

        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "failure")
        self.assertIn("already exist and overwrite was not requested", second.errors[0])

    def test_scaffold_supervised_run_force_overwrite_rewrites_artifacts(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        run_root = self.materialize_run(fixtures_root, runs_root, "run-1")

        first = scaffold_supervised_run(
            run_id="run-1",
            worker_role="implementation-worker",
            runs_root=runs_root,
        )
        handoff_path = run_root / "artifacts" / "handoff" / "worker-handoff.json"
        handoff_path.write_text("stale\n", encoding="utf-8")

        second = scaffold_supervised_run(
            run_id="run-1",
            worker_role="implementation-worker",
            force_overwrite=True,
            runs_root=runs_root,
        )

        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "success")
        self.assertTrue(second.overwritten_paths)
        handoff_payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        self.assertEqual(handoff_payload["task_id"], "issue-1")

    def test_cli_scaffold_supervised_run_text_success(self) -> None:
        run_id = f"cli-supervised-text-{uuid4().hex}"
        run_root = Path("c:/Users/jjmgo/coding_projects/agent-dev-swarm/sandbox/runs") / run_id
        self.addCleanup(lambda: shutil.rmtree(run_root, ignore_errors=True))

        materialize = self.run_cli(
            "materialize-sandbox-run",
            "--fixture",
            "tiny-calculator",
            "--run-id",
            run_id,
        )
        self.assertEqual(materialize.returncode, 0)

        completed = self.run_cli(
            "scaffold-supervised-run",
            "--run-id",
            run_id,
            "--worker-role",
            "implementation-worker",
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("scaffold-supervised-run: SUCCESS", completed.stdout)
        self.assertIn("summary: supervised run scaffold is ready for a bounded worker attempt.", completed.stdout)

    def test_cli_scaffold_supervised_run_json_failure_for_missing_run(self) -> None:
        completed = self.run_cli(
            "scaffold-supervised-run",
            "--run-id",
            f"missing-run-{uuid4().hex}",
            "--worker-role",
            "implementation-worker",
            "--format",
            "json",
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failure")
        self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()