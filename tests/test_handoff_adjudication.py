from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from agent_dev_swarm.handoff_adjudication import (
    adjudicate_worker_result_payload,
    build_worker_handoff,
    validate_worker_result_payload,
)


class HandoffAndAdjudicationTests(unittest.TestCase):
    def make_project(self, task_yaml: str | None = None) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
        if task_yaml is not None:
            task_dir = project_root / ".swarm" / "tasks"
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "issue-5.yaml").write_text(
                textwrap.dedent(task_yaml).strip() + "\n",
                encoding="utf-8",
            )
        return project_root

    def make_worker_result_file(self, payload: dict[str, object]) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        file_path = Path(temp_dir.name) / "worker-result.json"
        file_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return file_path

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "agent_dev_swarm.cli", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def valid_task_yaml(self) -> str:
        return """
        task_id: issue-5
        title: Add handoff and adjudication contract
        goal: Define the first explicit orchestrator to worker handoff and adjudication loop.
        scope:
          - Build the worker handoff payload from a task spec.
          - Validate worker result payloads.
          - Adjudicate results into accept, reject, retry, or escalate.
        non_goals:
          - Do not add live orchestration.
          - Do not call model provider APIs.
        required_outputs:
          - Worker handoff payload.
          - Adjudication result.
        success_criteria:
          - Handoff payload builds from a valid task spec.
          - Worker result payloads validate explicitly.
          - Adjudication returns deterministic decisions.
        notes: Keep the loop contract-driven and file-based.
        allowed_roots:
          - src
          - tests
        suggested_commands:
          - python -m unittest discover -s tests -v
        verification_commands:
          - python -m unittest discover -s tests -v
        implementation_record_path: .swarm/implementation-records/issue-5-handoff-and-adjudication.md
        """

    def valid_worker_result_payload(self) -> dict[str, object]:
        return {
            "task_id": "issue-5",
            "worker_role": "implementation-worker",
            "status": "success",
            "summary": "Built the control loop contract and verified the slice.",
            "actions_performed": [
                "Created the handoff builder.",
                "Created the adjudication validator.",
            ],
            "files_read": ["docs/orchestrator-worker-contract.md"],
            "files_changed": ["src/agent_dev_swarm/handoff_adjudication.py"],
            "commands_run": ["python -m unittest discover -s tests -v"],
            "command_results": [
                {
                    "command": "python -m unittest discover -s tests -v",
                    "outcome": "success",
                    "exit_code": 0,
                    "summary": "The test suite passed.",
                }
            ],
            "verification_status": "passed",
            "required_outputs_status": [
                {"name": "Worker handoff payload.", "status": "satisfied"},
                {"name": "Adjudication result.", "status": "satisfied"},
            ],
            "success_criteria_status": [
                {
                    "name": "Handoff payload builds from a valid task spec.",
                    "status": "satisfied",
                },
                {
                    "name": "Worker result payloads validate explicitly.",
                    "status": "satisfied",
                },
                {
                    "name": "Adjudication returns deterministic decisions.",
                    "status": "satisfied",
                },
            ],
            "unresolved_issues": [],
            "escalation_notes": [],
        }

    def retry_worker_result_payload(self) -> dict[str, object]:
        payload = self.valid_worker_result_payload()
        payload["status"] = "partial"
        payload["summary"] = "Completed part of the task but one output remains incomplete."
        payload["required_outputs_status"] = [
            {"name": "Worker handoff payload.", "status": "satisfied"},
            {"name": "Adjudication result.", "status": "partial", "details": "Needs one more validation case."},
        ]
        payload["success_criteria_status"] = [
            {
                "name": "Handoff payload builds from a valid task spec.",
                "status": "satisfied",
            },
            {
                "name": "Worker result payloads validate explicitly.",
                "status": "satisfied",
            },
            {
                "name": "Adjudication returns deterministic decisions.",
                "status": "partial",
                "details": "Retry and escalate cases still need review.",
            },
        ]
        payload["unresolved_issues"] = ["One remaining verification case is incomplete."]
        return payload

    def escalate_worker_result_payload(self) -> dict[str, object]:
        payload = self.valid_worker_result_payload()
        payload["status"] = "blocked"
        payload["summary"] = "Blocked on a design ambiguity in the escalation contract."
        payload["success_criteria_status"] = [
            {
                "name": "Handoff payload builds from a valid task spec.",
                "status": "satisfied",
            },
            {
                "name": "Worker result payloads validate explicitly.",
                "status": "satisfied",
            },
            {
                "name": "Adjudication returns deterministic decisions.",
                "status": "not_evaluated",
                "details": "Blocked on contract ambiguity.",
            },
        ]
        payload["unresolved_issues"] = ["Need orchestrator guidance on whether blocked results may carry partial acceptance." ]
        payload["escalation_notes"] = ["Escalate to the orchestrator to resolve the contract ambiguity."]
        return payload

    def test_build_worker_handoff_success(self) -> None:
        project_root = self.make_project(task_yaml=self.valid_task_yaml())

        result = build_worker_handoff(
            project_root=project_root,
            task="issue-5",
            worker_role="implementation-worker",
        )

        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.handoff)
        assert result.handoff is not None
        self.assertEqual(result.handoff.task_id, "issue-5")
        self.assertEqual(result.handoff.worker_role, "implementation-worker")
        self.assertIn("success_criteria_status", result.handoff.expected_result_fields)

    def test_build_worker_handoff_fails_for_invalid_task_spec(self) -> None:
        project_root = self.make_project(
            task_yaml="""
            task_id: issue-5
            title: Add handoff and adjudication contract
            goal: Define the first explicit orchestrator to worker handoff and adjudication loop.
            scope: []
            non_goals:
              - Do not add live orchestration.
            required_outputs:
              - Worker handoff payload.
            success_criteria:
              - Handoff payload builds from a valid task spec.
            """
        )

        result = build_worker_handoff(
            project_root=project_root,
            task="issue-5",
            worker_role="implementation-worker",
        )

        self.assertEqual(result.status, "failure")
        self.assertTrue(result.errors)

    def test_validate_worker_result_fails_when_field_missing(self) -> None:
        payload = self.valid_worker_result_payload()
        del payload["summary"]

        result = validate_worker_result_payload(payload)

        self.assertEqual(result.status, "failure")
        self.assertIn("Missing required worker result fields: summary", result.errors[0])

    def test_validate_worker_result_fails_when_type_invalid(self) -> None:
        payload = self.valid_worker_result_payload()
        payload["commands_run"] = "python -m unittest discover -s tests -v"

        result = validate_worker_result_payload(payload)

        self.assertEqual(result.status, "failure")
        self.assertIn("Field 'commands_run' must be a list of non-empty strings.", result.errors[0])

    def test_validate_worker_result_fails_when_enum_invalid(self) -> None:
        payload = self.valid_worker_result_payload()
        payload["status"] = "done"

        result = validate_worker_result_payload(payload)

        self.assertEqual(result.status, "failure")
        self.assertIn("Worker result status must be one of", result.errors[0])

    def test_adjudicate_worker_result_accept(self) -> None:
        result = adjudicate_worker_result_payload(self.valid_worker_result_payload())

        self.assertEqual(result.decision, "accept")
        self.assertTrue(result.required_outputs_satisfied)
        self.assertTrue(result.success_criteria_satisfied)
        self.assertFalse(result.escalation_requested)

    def test_adjudicate_worker_result_retry(self) -> None:
        result = adjudicate_worker_result_payload(self.retry_worker_result_payload())

        self.assertEqual(result.decision, "retry")
        self.assertFalse(result.required_outputs_satisfied)
        self.assertFalse(result.success_criteria_satisfied)
        self.assertFalse(result.escalation_requested)

    def test_adjudicate_worker_result_escalate(self) -> None:
        result = adjudicate_worker_result_payload(self.escalate_worker_result_payload())

        self.assertEqual(result.decision, "escalate")
        self.assertTrue(result.escalation_requested)

    def test_adjudicate_worker_result_rejects_invalid_payload(self) -> None:
        payload = self.valid_worker_result_payload()
        del payload["task_id"]

        result = adjudicate_worker_result_payload(payload)

        self.assertEqual(result.decision, "reject")
        self.assertEqual(result.status, "rejected")

    def test_cli_build_worker_handoff_text_success(self) -> None:
        project_root = self.make_project(task_yaml=self.valid_task_yaml())

        completed = self.run_cli(
            "build-worker-handoff",
            "--project",
            str(project_root),
            "--task",
            "issue-5",
            "--worker-role",
            "implementation-worker",
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("build-worker-handoff: SUCCESS", completed.stdout)

    def test_cli_build_worker_handoff_json_success(self) -> None:
        project_root = self.make_project(task_yaml=self.valid_task_yaml())

        completed = self.run_cli(
            "build-worker-handoff",
            "--project",
            str(project_root),
            "--task",
            "issue-5",
            "--worker-role",
            "implementation-worker",
            "--format",
            "json",
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["handoff"]["worker_role"], "implementation-worker")

    def test_cli_adjudicate_worker_result_json_accept(self) -> None:
        input_path = self.make_worker_result_file(self.valid_worker_result_payload())

        completed = self.run_cli(
            "adjudicate-worker-result",
            "--input",
            str(input_path),
            "--format",
            "json",
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "accept")

    def test_cli_adjudicate_worker_result_text_escalate(self) -> None:
        input_path = self.make_worker_result_file(self.escalate_worker_result_payload())

        completed = self.run_cli(
            "adjudicate-worker-result",
            "--input",
            str(input_path),
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("adjudicate-worker-result: ESCALATE", completed.stdout)

    def test_cli_adjudicate_worker_result_rejects_invalid_payload(self) -> None:
        payload = self.valid_worker_result_payload()
        del payload["summary"]
        input_path = self.make_worker_result_file(payload)

        completed = self.run_cli(
            "adjudicate-worker-result",
            "--input",
            str(input_path),
            "--format",
            "json",
        )

        self.assertEqual(completed.returncode, 1)
        parsed = json.loads(completed.stdout)
        self.assertEqual(parsed["decision"], "reject")


if __name__ == "__main__":
    unittest.main()