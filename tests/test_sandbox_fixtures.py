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

from agent_dev_swarm.sandbox_fixtures import DEFAULT_RUNS_ROOT, materialize_sandbox_run


class SandboxFixtureTests(unittest.TestCase):
    def make_fixture(
        self,
        fixtures_root: Path,
        fixture_name: str = "tiny-sample",
        manifest_yaml: str | None = None,
    ) -> Path:
        fixture_root = fixtures_root / fixture_name
        source_root = fixture_root / "project"
        (source_root / "src").mkdir(parents=True, exist_ok=True)
        (source_root / ".swarm" / "tasks").mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("fixture\n", encoding="utf-8")
        (source_root / "src" / "tool.py").write_text("VALUE = 1\n", encoding="utf-8")
        (source_root / ".swarm" / "tasks" / "issue-1.yaml").write_text(
            "task_id: issue-1\n"
            "title: Tiny sandbox fixture\n"
            "goal: Validate sandbox materialization.\n"
            "scope:\n"
            "  - Materialize the fixture.\n"
            "non_goals:\n"
            "  - Do not run the task.\n"
            "required_outputs:\n"
            "  - Fresh workspace.\n"
            "success_criteria:\n"
            "  - Fixture content is copied.\n",
            encoding="utf-8",
        )
        (source_root / ".swarm" / "execution-policy.yaml").write_text(
            "allowed_roots:\n"
            "  - .\n"
            "allowed_command_prefixes:\n"
            "  - python -m unittest\n",
            encoding="utf-8",
        )
        manifest_text = manifest_yaml or """
        fixture_id: tiny-sample
        description: Small sandbox test fixture.
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
        default_task_spec: .swarm/tasks/issue-1.yaml
        default_policy: .swarm/execution-policy.yaml
        intended_outcome: accept
        """
        (fixture_root / "fixture.yaml").write_text(
            textwrap.dedent(manifest_text).strip() + "\n",
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

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "agent_dev_swarm.cli", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_materialize_sandbox_run_success(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)

        result = materialize_sandbox_run(
            fixture_name="tiny-sample",
            run_id="run-1",
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "success")
        self.assertFalse(result.reset_performed)
        self.assertTrue((runs_root / "run-1" / "workspace" / "src" / "tool.py").is_file())
        self.assertTrue((runs_root / "run-1" / "workspace" / ".swarm" / "results").is_dir())
        self.assertTrue((runs_root / "run-1" / "artifacts" / "worker-result").is_dir())
        self.assertIsNotNone(result.metadata_path)
        assert result.metadata_path is not None
        metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["fixture_name"], "tiny-sample")
        self.assertEqual(metadata["run_id"], "run-1")

    def test_materialize_sandbox_run_fails_when_fixture_missing(self) -> None:
        fixtures_root, runs_root = self.make_roots()

        result = materialize_sandbox_run(
            fixture_name="missing-fixture",
            run_id="run-1",
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing sandbox fixture directory", result.errors[0])

    def test_materialize_sandbox_run_fails_when_manifest_invalid(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        self.make_fixture(
            fixtures_root,
            manifest_yaml="""
            fixture_id: tiny-sample
            description: Broken sandbox test fixture.
            layout_version: "1"
            source_root: project
            editable_paths:
              - src
            read_only_paths:
              - README.md
            generated_paths:
              - .swarm/evidence
            intended_outcome: accept
            """,
        )

        result = materialize_sandbox_run(
            fixture_name="tiny-sample",
            run_id="run-1",
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing required sandbox fixture fields: materialized_paths", result.errors[0])

    def test_materialize_sandbox_run_fails_when_run_exists_without_reset(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)

        first = materialize_sandbox_run(
            fixture_name="tiny-sample",
            run_id="run-1",
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )
        second = materialize_sandbox_run(
            fixture_name="tiny-sample",
            run_id="run-1",
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )

        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "failure")
        self.assertIn("already exists and reset was not requested", second.errors[0])

    def test_materialize_sandbox_run_force_reset_recreates_run(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)

        first = materialize_sandbox_run(
            fixture_name="tiny-sample",
            run_id="run-1",
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )
        marker = runs_root / "run-1" / "workspace" / "marker.txt"
        marker.write_text("stale\n", encoding="utf-8")

        second = materialize_sandbox_run(
            fixture_name="tiny-sample",
            run_id="run-1",
            force_reset=True,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )

        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "success")
        self.assertTrue(second.reset_performed)
        self.assertFalse(marker.exists())
        self.assertTrue((runs_root / "run-1" / "workspace" / "src" / "tool.py").is_file())

    def test_materialize_sandbox_run_fails_when_manifest_references_missing_content(self) -> None:
        fixtures_root, runs_root = self.make_roots()
        self.make_fixture(
            fixtures_root,
            manifest_yaml="""
            fixture_id: tiny-sample
            description: Broken sandbox test fixture.
            layout_version: "1"
            source_root: project
            materialized_paths:
              - missing.txt
            editable_paths:
              - src
            read_only_paths:
              - README.md
            generated_paths:
              - .swarm/evidence
            intended_outcome: accept
            """,
        )

        result = materialize_sandbox_run(
            fixture_name="tiny-sample",
            run_id="run-1",
            fixtures_root=fixtures_root,
            runs_root=runs_root,
        )

        self.assertEqual(result.status, "failure")
        self.assertIn("references missing fixture content", result.errors[0])

    def test_cli_materialize_sandbox_run_text_success(self) -> None:
        run_id = f"cli-text-{uuid4().hex}"
        run_root = DEFAULT_RUNS_ROOT / run_id
        self.addCleanup(lambda: shutil.rmtree(run_root, ignore_errors=True))

        completed = self.run_cli(
            "materialize-sandbox-run",
            "--fixture",
            "tiny-calculator",
            "--run-id",
            run_id,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("materialize-sandbox-run: SUCCESS", completed.stdout)
        self.assertIn("summary: sandbox run workspace and artifact scaffold were materialized successfully.", completed.stdout)

    def test_cli_materialize_sandbox_run_json_failure_for_missing_fixture(self) -> None:
        run_id = f"cli-json-missing-{uuid4().hex}"
        run_root = DEFAULT_RUNS_ROOT / run_id
        self.addCleanup(lambda: shutil.rmtree(run_root, ignore_errors=True))

        completed = self.run_cli(
            "materialize-sandbox-run",
            "--fixture",
            "missing-fixture",
            "--run-id",
            run_id,
            "--format",
            "json",
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failure")
        self.assertEqual(payload["fixture_name"], "missing-fixture")
        self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()