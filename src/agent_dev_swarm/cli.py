from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_dev_swarm.execution_policy import (
    check_command_policy,
    format_policy_decision_summary,
)
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

    parser.error(f"Unsupported command: {args.subcommand}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())