from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import yaml

REQUIRED_POLICY_FIELDS = ("allowed_roots", "allowed_command_prefixes")


@dataclass(slots=True)
class PolicyCheck:
    name: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }


@dataclass(slots=True)
class ExecutionPolicy:
    project_root: Path
    policy_path: Path
    allowed_roots: list[Path]
    allowed_command_prefixes: list[str]
    blocked_command_patterns: list[str] = field(default_factory=list)
    timeout_seconds: int | None = None
    max_output_bytes: int | None = None
    allow_network: bool = False
    allow_package_install: bool = False
    allow_git_write: bool = False
    raw_policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_path": str(self.policy_path),
            "allowed_roots": [str(path) for path in self.allowed_roots],
            "allowed_command_prefixes": list(self.allowed_command_prefixes),
            "blocked_command_patterns": list(self.blocked_command_patterns),
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "allow_network": self.allow_network,
            "allow_package_install": self.allow_package_install,
            "allow_git_write": self.allow_git_write,
        }


@dataclass(slots=True)
class CommandPolicyDecision:
    status: str
    project_root: Path
    policy_path: Path
    requested_cwd: str
    resolved_cwd: Path
    command: list[str]
    checks: list[PolicyCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    matched_allowed_prefix: str | None = None
    matched_blocked_pattern: str | None = None
    policy: ExecutionPolicy | None = None

    @property
    def command_text(self) -> str:
        return " ".join(self.command)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": str(self.project_root),
            "policy_path": str(self.policy_path),
            "requested_cwd": self.requested_cwd,
            "resolved_cwd": str(self.resolved_cwd),
            "command": list(self.command),
            "command_text": self.command_text,
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "matched_allowed_prefix": self.matched_allowed_prefix,
            "matched_blocked_pattern": self.matched_blocked_pattern,
            "policy": self.policy.to_dict() if self.policy is not None else None,
        }


@dataclass(slots=True)
class CheckedCommandResult:
    status: str
    project_root: Path
    policy_path: Path
    requested_cwd: str
    resolved_cwd: Path
    command: list[str]
    checks: list[PolicyCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    matched_allowed_prefix: str | None = None
    matched_blocked_pattern: str | None = None
    policy: ExecutionPolicy | None = None
    execution_performed: bool = False
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False

    @property
    def command_text(self) -> str:
        return " ".join(self.command)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": str(self.project_root),
            "policy_path": str(self.policy_path),
            "requested_cwd": self.requested_cwd,
            "resolved_cwd": str(self.resolved_cwd),
            "command": list(self.command),
            "command_text": self.command_text,
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "matched_allowed_prefix": self.matched_allowed_prefix,
            "matched_blocked_pattern": self.matched_blocked_pattern,
            "policy": self.policy.to_dict() if self.policy is not None else None,
            "execution_performed": self.execution_performed,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
        }

    @classmethod
    def from_policy_decision(cls, decision: CommandPolicyDecision) -> CheckedCommandResult:
        return cls(
            status="refused" if decision.status == "refused" else "failure",
            project_root=decision.project_root,
            policy_path=decision.policy_path,
            requested_cwd=decision.requested_cwd,
            resolved_cwd=decision.resolved_cwd,
            command=list(decision.command),
            checks=list(decision.checks),
            errors=list(decision.errors),
            matched_allowed_prefix=decision.matched_allowed_prefix,
            matched_blocked_pattern=decision.matched_blocked_pattern,
            policy=decision.policy,
        )


class ExecutionPolicyError(ValueError):
    pass


def load_execution_policy(project_root: Path, policy_path: Path) -> ExecutionPolicy:
    project_root = project_root.expanduser().resolve()
    resolved_policy_path = _resolve_against_project(project_root, policy_path)

    if not resolved_policy_path.is_file():
        raise ExecutionPolicyError(f"Missing execution policy file: {resolved_policy_path}")

    raw_policy = _parse_policy_yaml(resolved_policy_path)
    if isinstance(raw_policy, str):
        raise ExecutionPolicyError(raw_policy)

    parsed_policy = _build_execution_policy(project_root, resolved_policy_path, raw_policy)
    if isinstance(parsed_policy, str):
        raise ExecutionPolicyError(parsed_policy)

    return parsed_policy


def check_command_policy(
    project_root: Path,
    policy_path: Path,
    cwd: Path,
    command: Sequence[str],
) -> CommandPolicyDecision:
    project_root = project_root.expanduser().resolve()
    resolved_policy_path = _resolve_against_project(project_root, policy_path)
    resolved_cwd = _resolve_against_project(project_root, cwd)
    command_list = list(command)

    result = CommandPolicyDecision(
        status="refused",
        project_root=project_root,
        policy_path=resolved_policy_path,
        requested_cwd=str(cwd),
        resolved_cwd=resolved_cwd,
        command=command_list,
    )

    if not command_list:
        message = "No command was provided for policy evaluation."
        result.checks.append(
            PolicyCheck(name="command_present", status="fail", message=message)
        )
        result.errors.append(message)
        return result

    if not resolved_policy_path.is_file():
        message = f"Missing execution policy file: {resolved_policy_path}"
        result.checks.append(
            PolicyCheck(name="policy_file_exists", status="fail", message=message)
        )
        result.errors.append(message)
        return result

    result.checks.append(
        PolicyCheck(
            name="policy_file_exists",
            status="pass",
            message=f"Found execution policy file: {resolved_policy_path}",
        )
    )

    raw_policy = _parse_policy_yaml(resolved_policy_path)
    if isinstance(raw_policy, str):
        result.checks.append(
            PolicyCheck(name="policy_parses", status="fail", message=raw_policy)
        )
        result.errors.append(raw_policy)
        return result

    result.checks.append(
        PolicyCheck(
            name="policy_parses",
            status="pass",
            message="Parsed execution policy YAML successfully.",
        )
    )

    parsed_policy = _build_execution_policy(project_root, resolved_policy_path, raw_policy)
    if isinstance(parsed_policy, str):
        result.checks.append(
            PolicyCheck(name="policy_fields_valid", status="fail", message=parsed_policy)
        )
        result.errors.append(parsed_policy)
        return result

    result.policy = parsed_policy
    result.checks.append(
        PolicyCheck(
            name="policy_fields_valid",
            status="pass",
            message="Execution policy fields are valid.",
        )
    )

    if _is_within_allowed_roots(resolved_cwd, parsed_policy.allowed_roots):
        result.checks.append(
            PolicyCheck(
                name="cwd_within_allowed_roots",
                status="pass",
                message=f"Working directory is inside an allowed root: {resolved_cwd}",
            )
        )
    else:
        message = (
            f"Working directory is outside allowed roots: {resolved_cwd}. "
            f"Allowed roots: {', '.join(str(path) for path in parsed_policy.allowed_roots)}"
        )
        result.checks.append(
            PolicyCheck(name="cwd_within_allowed_roots", status="fail", message=message)
        )
        result.errors.append(message)

    normalized_command = _normalize_command_text(command_list)
    matched_allowed_prefix = _match_allowed_prefix(
        normalized_command,
        parsed_policy.allowed_command_prefixes,
    )
    if matched_allowed_prefix is not None:
        result.matched_allowed_prefix = matched_allowed_prefix
        result.checks.append(
            PolicyCheck(
                name="command_matches_allowed_prefix",
                status="pass",
                message=f"Command matches allowed prefix: {matched_allowed_prefix}",
            )
        )
    else:
        message = (
            f"Command is not on the allowlist: {normalized_command}. "
            f"Allowed prefixes: {', '.join(parsed_policy.allowed_command_prefixes)}"
        )
        result.checks.append(
            PolicyCheck(
                name="command_matches_allowed_prefix",
                status="fail",
                message=message,
            )
        )
        result.errors.append(message)

    matched_blocked_pattern = _match_blocked_pattern(
        normalized_command,
        parsed_policy.blocked_command_patterns,
    )
    if matched_blocked_pattern is None:
        result.checks.append(
            PolicyCheck(
                name="command_blocked_pattern_absent",
                status="pass",
                message="Command does not match any blocked pattern.",
            )
        )
    else:
        result.matched_blocked_pattern = matched_blocked_pattern
        message = f"Command matches blocked pattern: {matched_blocked_pattern}"
        result.checks.append(
            PolicyCheck(
                name="command_blocked_pattern_absent",
                status="fail",
                message=message,
            )
        )
        result.errors.append(message)

    if not result.errors:
        result.status = "allowed"

    return result


def format_policy_decision_summary(result: CommandPolicyDecision) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")

    lines = [
        f"check-command-policy: {result.status.upper()}",
        f"project root: {result.project_root}",
        f"policy path: {result.policy_path}",
        f"cwd: {result.resolved_cwd}",
        f"command: {result.command_text}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
    ]

    if failed:
        lines.append("refusals:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")
    else:
        lines.append("summary: command is within the approved execution policy.")

    return "\n".join(lines)


def run_checked_command(
    project_root: Path,
    policy_path: Path,
    cwd: Path,
    command: Sequence[str],
) -> CheckedCommandResult:
    decision = check_command_policy(
        project_root=project_root,
        policy_path=policy_path,
        cwd=cwd,
        command=command,
    )
    result = CheckedCommandResult.from_policy_decision(decision)

    if decision.status != "allowed":
        result.status = "refused"
        return result

    if not result.resolved_cwd.is_dir():
        message = f"Working directory does not exist: {result.resolved_cwd}"
        result.checks.append(
            PolicyCheck(name="command_execution_started", status="fail", message=message)
        )
        result.errors.append(message)
        result.status = "failure"
        return result

    timeout_seconds = result.policy.timeout_seconds if result.policy is not None else None
    try:
        completed = subprocess.run(
            list(result.command),
            cwd=str(result.resolved_cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        result.execution_performed = True
        result.timed_out = True
        result.stdout = _coerce_stream_data(exc.stdout)
        result.stderr = _coerce_stream_data(exc.stderr)
        result.status = "timeout"
        message = f"Command exceeded timeout of {timeout_seconds} seconds."
        result.checks.append(
            PolicyCheck(name="command_execution_started", status="pass", message=f"Executed command in {result.resolved_cwd}"),
        )
        result.checks.append(
            PolicyCheck(name="command_exit_code_zero", status="fail", message=message)
        )
        result.errors.append(message)
        return result
    except OSError as exc:
        message = f"Failed to start command: {exc}"
        result.checks.append(
            PolicyCheck(name="command_execution_started", status="fail", message=message)
        )
        result.errors.append(message)
        result.status = "failure"
        return result

    result.execution_performed = True
    result.stdout = completed.stdout
    result.stderr = completed.stderr
    result.exit_code = completed.returncode
    result.checks.append(
        PolicyCheck(
            name="command_execution_started",
            status="pass",
            message=f"Executed command in {result.resolved_cwd}",
        )
    )

    if completed.returncode == 0:
        result.checks.append(
            PolicyCheck(
                name="command_exit_code_zero",
                status="pass",
                message="Command exited with status code 0.",
            )
        )
        result.status = "success"
        return result

    message = f"Command exited with nonzero status: {completed.returncode}"
    result.checks.append(
        PolicyCheck(
            name="command_exit_code_zero",
            status="fail",
            message=message,
        )
    )
    result.errors.append(message)
    result.status = "failure"
    return result


def format_checked_command_summary(result: CheckedCommandResult) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")

    lines = [
        f"run-checked-command: {result.status.upper()}",
        f"project root: {result.project_root}",
        f"policy path: {result.policy_path}",
        f"cwd: {result.resolved_cwd}",
        f"command: {result.command_text}",
        f"execution performed: {'yes' if result.execution_performed else 'no'}",
        f"exit code: {result.exit_code if result.exit_code is not None else 'none'}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
    ]

    if failed:
        lines.append("failures:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")
    else:
        lines.append("summary: command executed within the approved execution policy.")

    if result.stdout:
        lines.append("stdout:")
        lines.append(result.stdout.rstrip())

    if result.stderr:
        lines.append("stderr:")
        lines.append(result.stderr.rstrip())

    return "\n".join(lines)


def _parse_policy_yaml(policy_path: Path) -> dict[str, Any] | str:
    try:
        with policy_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return f"Failed to parse execution policy YAML in {policy_path}: {exc}"
    except OSError as exc:
        return f"Failed to read execution policy file {policy_path}: {exc}"

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        return f"Expected YAML mapping in {policy_path}, got {type(loaded).__name__}."
    return loaded


def _build_execution_policy(
    project_root: Path,
    policy_path: Path,
    raw_policy: dict[str, Any],
) -> ExecutionPolicy | str:
    missing_fields = [field for field in REQUIRED_POLICY_FIELDS if field not in raw_policy]
    if missing_fields:
        return "Missing required policy fields: " + ", ".join(missing_fields)

    allowed_roots = _get_non_empty_string_list(raw_policy, "allowed_roots")
    if isinstance(allowed_roots, str):
        return allowed_roots

    allowed_command_prefixes = _get_non_empty_string_list(raw_policy, "allowed_command_prefixes")
    if isinstance(allowed_command_prefixes, str):
        return allowed_command_prefixes

    blocked_command_patterns = _get_optional_string_list(raw_policy, "blocked_command_patterns")
    if isinstance(blocked_command_patterns, str):
        return blocked_command_patterns

    timeout_seconds = _get_optional_positive_int(raw_policy, "timeout_seconds")
    if isinstance(timeout_seconds, str):
        return timeout_seconds

    max_output_bytes = _get_optional_positive_int(raw_policy, "max_output_bytes")
    if isinstance(max_output_bytes, str):
        return max_output_bytes

    allow_network = _get_optional_bool(raw_policy, "allow_network", default=False)
    if isinstance(allow_network, str):
        return allow_network

    allow_package_install = _get_optional_bool(raw_policy, "allow_package_install", default=False)
    if isinstance(allow_package_install, str):
        return allow_package_install

    allow_git_write = _get_optional_bool(raw_policy, "allow_git_write", default=False)
    if isinstance(allow_git_write, str):
        return allow_git_write

    return ExecutionPolicy(
        project_root=project_root,
        policy_path=policy_path,
        allowed_roots=[_resolve_against_project(project_root, Path(value)) for value in allowed_roots],
        allowed_command_prefixes=[_normalize_command_text(value.split()) for value in allowed_command_prefixes],
        blocked_command_patterns=[_normalize_command_text(value.split()) for value in blocked_command_patterns],
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        allow_network=allow_network,
        allow_package_install=allow_package_install,
        allow_git_write=allow_git_write,
        raw_policy=raw_policy,
    )


def _get_non_empty_string_list(raw_policy: dict[str, Any], field_name: str) -> list[str] | str:
    value = raw_policy.get(field_name)
    if not isinstance(value, list) or not value:
        return f"Policy field {field_name} must be a non-empty list of strings."

    normalized_values: list[str] = []
    for item in value:
        if not isinstance(item, str) or item.strip() == "":
            return f"Policy field {field_name} must contain only non-empty strings."
        normalized_values.append(item.strip())
    return normalized_values


def _get_optional_string_list(raw_policy: dict[str, Any], field_name: str) -> list[str] | str:
    value = raw_policy.get(field_name)
    if value is None:
        return []
    if not isinstance(value, list):
        return f"Policy field {field_name} must be a list of strings when provided."

    normalized_values: list[str] = []
    for item in value:
        if not isinstance(item, str) or item.strip() == "":
            return f"Policy field {field_name} must contain only non-empty strings."
        normalized_values.append(item.strip())
    return normalized_values


def _get_optional_positive_int(raw_policy: dict[str, Any], field_name: str) -> int | None | str:
    value = raw_policy.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return f"Policy field {field_name} must be a positive integer when provided."
    return value


def _get_optional_bool(raw_policy: dict[str, Any], field_name: str, default: bool) -> bool | str:
    value = raw_policy.get(field_name)
    if value is None:
        return default
    if not isinstance(value, bool):
        return f"Policy field {field_name} must be a boolean when provided."
    return value


def _resolve_against_project(project_root: Path, candidate: Path) -> Path:
    expanded = candidate.expanduser()
    if not expanded.is_absolute():
        expanded = project_root / expanded
    return expanded.resolve()


def _is_within_allowed_roots(path: Path, allowed_roots: Sequence[Path]) -> bool:
    return any(_is_relative_to(path, root) for root in allowed_roots)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalize_command_text(command: Sequence[str]) -> str:
    return " ".join(part for part in " ".join(command).split() if part)


def _match_allowed_prefix(command_text: str, allowed_prefixes: Sequence[str]) -> str | None:
    for prefix in allowed_prefixes:
        if command_text.startswith(prefix):
            return prefix
    return None


def _match_blocked_pattern(command_text: str, blocked_patterns: Sequence[str]) -> str | None:
    for pattern in blocked_patterns:
        if pattern and pattern in command_text:
            return pattern
    return None


def _coerce_stream_data(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value