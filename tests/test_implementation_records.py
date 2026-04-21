from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_dev_swarm.implementation_records import (
    ImplementationRecordDraft,
    ImplementationRecordError,
    build_record_id,
    init_implementation_record,
)


class ImplementationRecordTests(unittest.TestCase):
    def make_output_path(self, file_name: str = "record.md") -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return Path(temp_dir.name) / file_name

    def run_cli(self, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_dev_swarm.cli",
                "init-implementation-record",
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_build_record_id_slugifies_inputs(self) -> None:
        self.assertEqual(
            build_record_id("Issue 2", "Define implementation record convention"),
            "issue-2-define-implementation-record-convention",
        )

    def test_init_implementation_record_writes_expected_sections(self) -> None:
        output_path = self.make_output_path()

        result = init_implementation_record(
            ImplementationRecordDraft(
                task_id="2",
                title="Define implementation record convention",
                goal="Add a lightweight implementation record convention.",
                output_path=output_path,
                scope=["Document the convention", "Add a scaffolding helper"],
                non_goals=["Do not add workflow orchestration"],
                files_changed=["docs/implementation-records.md"],
                commands=["python -m unittest discover -s tests -v"],
                evidence_refs=[".swarm/evidence/validate-project.json"],
            )
        )

        self.assertEqual(result.status, "created")
        contents = output_path.read_text(encoding="utf-8")
        self.assertIn("# Implementation Record", contents)
        self.assertIn("- Task/Issue ID: 2", contents)
        self.assertIn("## Scope", contents)
        self.assertIn("- Document the convention", contents)
        self.assertIn("## Structured Evidence", contents)
        self.assertIn(".swarm/evidence/validate-project.json", contents)
        self.assertIn("## Commands Run", contents)
        self.assertIn("- Command: python -m unittest discover -s tests -v", contents)

    def test_init_implementation_record_refuses_existing_file(self) -> None:
        output_path = self.make_output_path()
        output_path.write_text("existing\n", encoding="utf-8")

        with self.assertRaises(ImplementationRecordError):
            init_implementation_record(
                ImplementationRecordDraft(
                    task_id="2",
                    title="Define implementation record convention",
                    goal="Add a lightweight implementation record convention.",
                    output_path=output_path,
                )
            )

    def test_cli_init_implementation_record_text_success(self) -> None:
        output_path = self.make_output_path()

        completed = self.run_cli(
            "--issue",
            "2",
            "--title",
            "Define implementation record convention",
            "--goal",
            "Add a lightweight implementation record convention.",
            "--output",
            str(output_path),
            "--scope",
            "Document the convention",
            "--non-goal",
            "Do not add orchestration",
            "--command",
            "python -m unittest discover -s tests -v",
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("init-implementation-record: CREATED", completed.stdout)
        self.assertTrue(output_path.is_file())

    def test_cli_init_implementation_record_json_failure_when_file_exists(self) -> None:
        output_path = self.make_output_path()
        output_path.write_text("existing\n", encoding="utf-8")

        completed = self.run_cli(
            "--issue",
            "2",
            "--title",
            "Define implementation record convention",
            "--output",
            str(output_path),
            "--format",
            "json",
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failure")
        self.assertIn("already exists", payload["error"])


if __name__ == "__main__":
    unittest.main()