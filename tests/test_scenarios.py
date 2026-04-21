from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from agent_dev_swarm.cli import main
from agent_dev_swarm.scenarios import (
    LocalWorkerInvocationResult,
    ScenarioRunResult,
    load_scenario,
    run_scenario,
)


class ScenarioTests(unittest.TestCase):
    def make_fixture(self, fixtures_root: Path, fixture_name: str = "tiny-scenario") -> Path:
        fixture_root = fixtures_root / fixture_name
        source_root = fixture_root / "project"
        (source_root / "src").mkdir(parents=True, exist_ok=True)
        (source_root / "tests").mkdir(parents=True, exist_ok=True)
        (source_root / ".swarm" / "tasks").mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("fixture\n", encoding="utf-8")
        (source_root / "src" / "calculator.py").write_text(
            "def add(left: int, right: int) -> int:\n    return left + right\n",
            encoding="utf-8",
        )
        (source_root / "tests" / "test_calculator.py").write_text(
            "import unittest\n\n"
            "from src.calculator import add\n\n"
            "class CalculatorTests(unittest.TestCase):\n"
            "    def test_add(self) -> None:\n"
            "        self.assertEqual(add(2, 3), 5)\n",
            encoding="utf-8",
        )
        (source_root / ".swarm" / "tasks" / "issue-1.yaml").write_text(
            textwrap.dedent(
                """
                task_id: issue-1
                title: Propose subtract change
                goal: Review the tiny calculator fixture and prepare a conservative worker response.
                scope:
                  - Inspect src/calculator.py and tests/test_calculator.py.
                  - Describe the subtract addition.
                non_goals:
                  - Do not claim file edits.
                required_outputs:
                  - Raw local worker response artifact.
                  - Reviewable worker-result artifact or starter artifact.
                success_criteria:
                  - Raw output is captured.
                  - Worker-result state remains conservative.
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
                """
                fixture_id: tiny-scenario
                description: Small scenario test fixture.
                layout_version: "1"
                source_root: project
                materialized_paths:
                  - README.md
                  - src
                  - tests
                  - .swarm/tasks
                  - .swarm/execution-policy.yaml
                editable_paths:
                  - src
                read_only_paths:
                  - README.md
                  - tests
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

    def make_roots(self) -> tuple[Path, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        temp_root = Path(temp_dir.name)
        scenarios_root = temp_root / "scenarios"
        fixtures_root = temp_root / "fixtures"
        runs_root = temp_root / "runs"
        scenarios_root.mkdir(parents=True, exist_ok=True)
        fixtures_root.mkdir(parents=True, exist_ok=True)
        runs_root.mkdir(parents=True, exist_ok=True)
        return scenarios_root, fixtures_root, runs_root

    def make_scenario(self, scenarios_root: Path, scenario_yaml: str | None = None) -> Path:
        scenario_path = scenarios_root / "scenario-1.yaml"
        scenario_path.write_text(
            textwrap.dedent(
                scenario_yaml
                or """
                scenario_id: scenario-1
                description: Test scenario for local-only runner.
                scenario_version: "1"
                fixture: tiny-scenario
                task: .swarm/tasks/issue-1.yaml
                policy: .swarm/execution-policy.yaml
                worker_role: implementation-worker
                provider: ollama
                model: phi4-mini:latest
                allow_remote_models: false
                reset_before_run: true
                expected_outcome: reviewable-local-worker-output
                run_id_prefix: scenario-1
                context_files:
                  - src/calculator.py
                  - tests/test_calculator.py
                timeout_seconds: 60
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return scenario_path

    def fake_invoker(self, model: str, prompt: str, timeout_seconds: int | None) -> LocalWorkerInvocationResult:
        self.assertTrue(prompt)
        self.assertEqual(model, "phi4-mini:latest")
        self.assertEqual(timeout_seconds, 60)
        payload = {
            "task_id": "issue-1",
            "worker_role": "implementation-worker",
            "status": "partial",
            "summary": "Reviewed the subtract change and left the task in a conservative reviewable state.",
            "actions_performed": [
                "Reviewed the worker handoff requirements.",
                "Inspected the provided code context.",
            ],
            "files_read": ["src/calculator.py", "tests/test_calculator.py"],
            "files_changed": [],
            "commands_run": [],
            "command_results": [],
            "verification_status": "not_run",
            "required_outputs_status": [
                {"name": "Raw local worker response artifact.", "status": "not_evaluated"},
                {"name": "Reviewable worker-result artifact or starter artifact.", "status": "not_evaluated"},
            ],
            "success_criteria_status": [
                {"name": "Raw output is captured.", "status": "not_evaluated"},
                {"name": "Worker-result state remains conservative.", "status": "not_evaluated"},
            ],
            "unresolved_issues": [
                "No file edits or test execution were performed by the local-only scenario runner.",
            ],
            "escalation_notes": [],
        }
        return LocalWorkerInvocationResult(
            status="success",
            provider="ollama",
            model=model,
            command=["ollama", "run", model, "<prompt>"],
            raw_output=json.dumps(payload, indent=2),
            stderr="",
            exit_code=0,
            timed_out=False,
            error=None,
        )

    def fake_invoker_with_preamble(
        self,
        model: str,
        prompt: str,
        timeout_seconds: int | None,
    ) -> LocalWorkerInvocationResult:
        result = self.fake_invoker(model, prompt, timeout_seconds)
        result.raw_output = "Thinking...\n\x1b[4D\x1b[K\n...done thinking.\n\n" + result.raw_output
        return result

    def fake_invoker_with_status_aliases(
        self,
        model: str,
        prompt: str,
        timeout_seconds: int | None,
    ) -> LocalWorkerInvocationResult:
        result = self.fake_invoker(model, prompt, timeout_seconds)
        payload = json.loads(result.raw_output)
        payload["required_outputs_status"][0]["status"] = "completed"
        payload["required_outputs_status"][1]["status"] = "pending"
        payload["success_criteria_status"][0]["status"] = "completed"
        payload["success_criteria_status"][1]["status"] = "pending"
        result.raw_output = json.dumps(payload, indent=2)
        return result

    def test_load_scenario_success(self) -> None:
        scenarios_root, fixtures_root, _runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(scenarios_root)

        result = load_scenario("scenario-1", scenarios_root=scenarios_root)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.scenario_id, "scenario-1")
        self.assertIsNotNone(result.scenario)
        assert result.scenario is not None
        self.assertEqual(result.scenario.provider, "ollama")
        self.assertFalse(result.scenario.allow_remote_models)

    def test_load_scenario_fails_when_missing(self) -> None:
        scenarios_root, _fixtures_root, _runs_root = self.make_roots()

        result = load_scenario("scenario-1", scenarios_root=scenarios_root)

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing scenario file", result.errors[0])

    def test_load_scenario_fails_when_invalid_manifest(self) -> None:
        scenarios_root, fixtures_root, _runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(
            scenarios_root,
            scenario_yaml="""
            scenario_id: scenario-1
            description: Broken scenario
            scenario_version: "1"
            fixture: tiny-scenario
            worker_role: implementation-worker
            provider: ollama
            allow_remote_models: false
            reset_before_run: true
            expected_outcome: reviewable-local-worker-output
            """,
        )

        result = load_scenario("scenario-1", scenarios_root=scenarios_root)

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing required scenario fields: model", result.errors[0])

    def test_load_scenario_rejects_remote_models(self) -> None:
        scenarios_root, fixtures_root, _runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(
            scenarios_root,
            scenario_yaml="""
            scenario_id: scenario-1
            description: Invalid remote scenario
            scenario_version: "1"
            fixture: tiny-scenario
            worker_role: implementation-worker
            provider: ollama
            model: phi4-mini:latest
            allow_remote_models: true
            reset_before_run: true
            expected_outcome: reviewable-local-worker-output
            """,
        )

        result = load_scenario("scenario-1", scenarios_root=scenarios_root)

        self.assertEqual(result.status, "failure")
        self.assertIn("allow_remote_models: false", result.errors[0])

    def test_load_scenario_rejects_unsupported_provider(self) -> None:
        scenarios_root, fixtures_root, _runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(
            scenarios_root,
            scenario_yaml="""
            scenario_id: scenario-1
            description: Unsupported provider scenario
            scenario_version: "1"
            fixture: tiny-scenario
            worker_role: implementation-worker
            provider: openai
            model: gpt-test
            allow_remote_models: false
            reset_before_run: true
            expected_outcome: reviewable-local-worker-output
            """,
        )

        result = load_scenario("scenario-1", scenarios_root=scenarios_root)

        self.assertEqual(result.status, "failure")
        self.assertIn("Unsupported scenario provider 'openai'", result.errors[0])

    def test_run_scenario_success_with_mocked_invoker(self) -> None:
        scenarios_root, fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(scenarios_root)

        result = run_scenario(
            "scenario-1",
            scenarios_root=scenarios_root,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
            invoker=self.fake_invoker,
        )

        self.assertEqual(result.status, "success")
        self.assertTrue((runs_root / "scenario-1" / "workspace" / "src" / "calculator.py").is_file())
        self.assertIsNotNone(result.handoff_path)
        self.assertIsNotNone(result.worker_result_starter_path)
        self.assertIsNotNone(result.raw_output_path)
        self.assertIsNotNone(result.scenario_summary_path)
        self.assertTrue(result.candidate_result_written)
        assert result.worker_result_path is not None
        worker_result = json.loads(result.worker_result_path.read_text(encoding="utf-8"))
        self.assertEqual(worker_result["task_id"], "issue-1")
        self.assertEqual(worker_result["worker_role"], "implementation-worker")

    def test_run_scenario_extracts_candidate_from_prefixed_output(self) -> None:
        scenarios_root, fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(scenarios_root)

        result = run_scenario(
            "scenario-1",
            scenarios_root=scenarios_root,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
            invoker=self.fake_invoker_with_preamble,
        )

        self.assertEqual(result.status, "success")
        self.assertTrue(result.candidate_result_written)
        assert result.worker_result_path is not None
        payload = json.loads(result.worker_result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "partial")

    def test_run_scenario_normalizes_common_status_aliases(self) -> None:
        scenarios_root, fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(scenarios_root)

        result = run_scenario(
            "scenario-1",
            scenarios_root=scenarios_root,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
            invoker=self.fake_invoker_with_status_aliases,
        )

        self.assertEqual(result.status, "success")
        self.assertTrue(result.candidate_result_written)
        assert result.worker_result_path is not None
        payload = json.loads(result.worker_result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["required_outputs_status"][0]["status"], "satisfied")
        self.assertEqual(payload["required_outputs_status"][1]["status"], "not_evaluated")

    def test_run_scenario_fails_when_task_reference_missing(self) -> None:
        scenarios_root, fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(
            scenarios_root,
            scenario_yaml="""
            scenario_id: scenario-1
            description: Missing task scenario
            scenario_version: "1"
            fixture: tiny-scenario
            task: .swarm/tasks/missing.yaml
            worker_role: implementation-worker
            provider: ollama
            model: phi4-mini:latest
            allow_remote_models: false
            reset_before_run: true
            expected_outcome: reviewable-local-worker-output
            """,
        )

        result = run_scenario(
            "scenario-1",
            scenarios_root=scenarios_root,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
            invoker=self.fake_invoker,
        )

        self.assertEqual(result.status, "failure")
        self.assertTrue(any("Resolved task spec file does not exist" in error for error in result.errors))

    def test_run_scenario_stops_on_local_only_validation_failure(self) -> None:
        scenarios_root, fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(
            scenarios_root,
            scenario_yaml="""
            scenario_id: scenario-1
            description: Invalid local-only scenario
            scenario_version: "1"
            fixture: tiny-scenario
            worker_role: implementation-worker
            provider: ollama
            model: phi4-mini:latest
            allow_remote_models: true
            reset_before_run: true
            expected_outcome: reviewable-local-worker-output
            """,
        )

        result = run_scenario(
            "scenario-1",
            scenarios_root=scenarios_root,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
            invoker=self.fake_invoker,
        )

        self.assertEqual(result.status, "failure")
        self.assertIn("allow_remote_models: false", result.errors[0])
        self.assertFalse((runs_root / "scenario-1").exists())

    def test_scenario_run_result_to_dict_contains_expected_keys(self) -> None:
        scenarios_root, fixtures_root, runs_root = self.make_roots()
        self.make_fixture(fixtures_root)
        self.make_scenario(scenarios_root)

        result = run_scenario(
            "scenario-1",
            scenarios_root=scenarios_root,
            fixtures_root=fixtures_root,
            runs_root=runs_root,
            invoker=self.fake_invoker,
        )

        payload = result.to_dict()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["scenario_id"], "scenario-1")
        self.assertIn("raw_output_path", payload)
        self.assertIn("scenario_summary_path", payload)
        self.assertEqual(payload["provider"], "ollama")

    def test_cli_run_scenario_text_success_with_patch(self) -> None:
        fake_result = ScenarioRunResult(
            status="success",
            scenario_id="scenario-1",
            scenario_path=Path("scenario-1.yaml"),
            run_id="scenario-1",
            run_root=Path("sandbox/runs/scenario-1"),
            workspace_root=Path("sandbox/runs/scenario-1/workspace"),
            artifacts_root=Path("sandbox/runs/scenario-1/artifacts"),
            fixture="tiny-calculator",
            worker_role="implementation-worker",
            provider="ollama",
            model="phi4-mini:latest",
        )
        buffer = StringIO()

        with patch("agent_dev_swarm.cli.run_scenario", return_value=fake_result):
            with redirect_stdout(buffer):
                exit_code = main(["run-scenario", "scenario-1"])

        self.assertEqual(exit_code, 0)
        self.assertIn("run-scenario: SUCCESS", buffer.getvalue())

    def test_cli_run_scenario_json_failure_with_patch(self) -> None:
        fake_result = ScenarioRunResult(
            status="failure",
            scenario_id="scenario-1",
            scenario_path=Path("scenario-1.yaml"),
            run_id="scenario-1",
            run_root=Path("sandbox/runs/scenario-1"),
            workspace_root=Path("sandbox/runs/scenario-1/workspace"),
            artifacts_root=Path("sandbox/runs/scenario-1/artifacts"),
            fixture="tiny-calculator",
            worker_role="implementation-worker",
            provider="ollama",
            model="phi4-mini:latest",
            errors=["failure"],
        )
        buffer = StringIO()

        with patch("agent_dev_swarm.cli.run_scenario", return_value=fake_result):
            with redirect_stdout(buffer):
                exit_code = main(["run-scenario", "scenario-1", "--format", "json"])

        self.assertEqual(exit_code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["status"], "failure")
        self.assertEqual(payload["scenario_id"], "scenario-1")


if __name__ == "__main__":
    unittest.main()