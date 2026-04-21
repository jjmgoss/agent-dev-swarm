from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_dev_swarm.execution_policy import (
    check_command_policy,
    format_checked_command_summary,
    format_policy_decision_summary,
    run_checked_command,
)
from agent_dev_swarm.implementation_records import (
    ImplementationRecordDraft,
    ImplementationRecordError,
    format_implementation_record_init_summary,
    init_implementation_record,
)
from agent_dev_swarm.task_specs import format_task_spec_summary, load_task_spec
from agent_dev_swarm.validate_project import format_terminal_summary, validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="swarm")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    validate_parser = subparsers.add_parser(
        "validate-project",
        help="Validate that a target project is attached to the framework",
    )
    validate_parser.add_argument(
        "--project",
        required=True,
        help="Path to the target project root",
    )
    validate_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for validation results",
    )

    policy_parser = subparsers.add_parser(
        "check-command-policy",
        help="Evaluate a proposed command against an execution policy without running it",
    )
    policy_parser.add_argument(
        "--project",
        required=True,
        help="Path to the target project root",
    )
    policy_parser.add_argument(
        "--policy",
        required=True,
        help="Path to the execution policy file",
    )
    policy_parser.add_argument(
        "--cwd",
        required=True,
        help="Proposed working directory for the command",
    )
    policy_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the policy decision",
    )
    policy_parser.add_argument(
        "candidate_command",
        nargs=argparse.REMAINDER,
        help="Command to evaluate; pass it after --",
    )

    run_parser = subparsers.add_parser(
        "run-checked-command",
        help="Execute one command only if it is allowed by the execution policy",
    )
    run_parser.add_argument(
        "--project",
        required=True,
        help="Path to the target project root",
    )
    run_parser.add_argument(
        "--policy",
        required=True,
        help="Path to the execution policy file",
    )
    run_parser.add_argument(
        "--cwd",
        required=True,
        help="Working directory to use if execution is allowed",
    )
    run_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the execution result",
    )
    run_parser.add_argument(
        "candidate_command",
        nargs=argparse.REMAINDER,
        help="Command to execute; pass it after --",
    )

    record_parser = subparsers.add_parser(
        "init-implementation-record",
        help="Create a starter implementation record for one bounded task",
    )
    record_parser.add_argument(
        "--task-id",
        "--issue",
        dest="task_id",
        required=True,
        help="Task or issue identifier for the record",
    )
    record_parser.add_argument(
        "--title",
        required=True,
        help="Short title for the bounded task",
    )
    record_parser.add_argument(
        "--goal",
        default="",
        help="Optional goal statement for the bounded task",
    )
    record_parser.add_argument(
        "--output",
        required=True,
        help="Path where the implementation record should be written",
    )
    record_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the scaffold result",
    )
    record_parser.add_argument(
        "--status",
        choices=("in_progress", "accept", "retry", "escalate"),
        default="in_progress",
        help="Initial final-status value for the record",
    )
    record_parser.add_argument(
        "--verification-status",
        choices=("not_run", "passed", "failed", "mixed"),
        default="not_run",
        help="Initial verification status for the record",
    )
    record_parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Optional scope bullet to prefill; may be repeated",
    )
    record_parser.add_argument(
        "--non-goal",
        action="append",
        default=[],
        help="Optional non-goal bullet to prefill; may be repeated",
    )
    record_parser.add_argument(
        "--file",
        dest="files_changed",
        action="append",
        default=[],
        help="Optional changed file path to prefill; may be repeated",
    )
    record_parser.add_argument(
        "--command",
        action="append",
        default=[],
        help="Optional command text to prefill; may be repeated",
    )
    record_parser.add_argument(
        "--evidence-ref",
        action="append",
        default=[],
        help="Optional structured evidence reference to prefill; may be repeated",
    )

    task_parser = subparsers.add_parser(
        "load-task-spec",
        help="Load and validate one bounded task spec from a target project",
    )
    task_parser.add_argument(
        "--project",
        required=True,
        help="Path to the target project root",
    )
    task_parser.add_argument(
        "--task",
        required=True,
        help="Task id or path to the task spec file",
    )
    task_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the task spec result",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "validate-project":
        result = validate_project(Path(args.project))
        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_terminal_summary(result))
        return 0 if result.status == "success" else 1

    if args.subcommand == "check-command-policy":
        command = list(args.candidate_command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            parser.error("check-command-policy requires a command after --")

        result = check_command_policy(
            project_root=Path(args.project),
            policy_path=Path(args.policy),
            cwd=Path(args.cwd),
            command=command,
        )
        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_policy_decision_summary(result))
        return 0 if result.status == "allowed" else 1

    if args.subcommand == "run-checked-command":
        command = list(args.candidate_command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            parser.error("run-checked-command requires a command after --")

        result = run_checked_command(
            project_root=Path(args.project),
            policy_path=Path(args.policy),
            cwd=Path(args.cwd),
            command=command,
        )
        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_checked_command_summary(result))

        if result.status == "success":
            return 0
        if result.status == "failure" and result.execution_performed and result.exit_code is not None:
            return result.exit_code
        if result.status == "timeout":
            return 124
        return 1

    if args.subcommand == "init-implementation-record":
        try:
            result = init_implementation_record(
                ImplementationRecordDraft(
                    task_id=args.task_id,
                    title=args.title,
                    goal=args.goal,
                    output_path=Path(args.output),
                    final_status=args.status,
                    verification_status=args.verification_status,
                    scope=list(args.scope),
                    non_goals=list(args.non_goal),
                    files_changed=list(args.files_changed),
                    commands=list(args.command),
                    evidence_refs=list(args.evidence_ref),
                )
            )
        except ImplementationRecordError as exc:
            if args.format == "json":
                print(json.dumps({"status": "failure", "error": str(exc)}, indent=2))
            else:
                print("init-implementation-record: FAILURE")
                print(f"error: {exc}")
            return 1

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_implementation_record_init_summary(result))
        return 0

    if args.subcommand == "load-task-spec":
        result = load_task_spec(project_root=Path(args.project), task=args.task)
        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_task_spec_summary(result))
        return 0 if result.status == "success" else 1

    parser.error(f"Unsupported command: {args.subcommand}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())