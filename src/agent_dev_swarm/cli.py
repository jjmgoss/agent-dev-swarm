from __future__ import annotations

import argparse
from pathlib import Path

from agent_dev_swarm.validate_project import format_terminal_summary, validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="swarm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-project",
        help="Validate that a target project is attached to the framework",
    )
    validate_parser.add_argument(
        "--project",
        required=True,
        help="Path to the target project root",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-project":
        result = validate_project(Path(args.project))
        print(format_terminal_summary(result))
        return 0 if result.status == "success" else 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())