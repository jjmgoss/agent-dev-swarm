from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_STRING_FIELDS = ("task_id", "title", "goal")
REQUIRED_LIST_FIELDS = ("scope", "non_goals", "required_outputs", "success_criteria")
OPTIONAL_STRING_FIELDS = ("notes", "implementation_record_path")
OPTIONAL_LIST_FIELDS = ("allowed_roots", "suggested_commands", "verification_commands")


@dataclass(slots=True)
class TaskSpecCheck:
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
class NormalizedTaskSpec:
    task_id: str
    title: str
    goal: str
    scope: list[str]
    non_goals: list[str]
    required_outputs: list[str]
    success_criteria: list[str]
    notes: str | None = None
    allowed_roots: list[str] | None = None
    suggested_commands: list[str] | None = None
    verification_commands: list[str] | None = None
    implementation_record_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_id": self.task_id,
            "title": self.title,
            "goal": self.goal,
            "scope": list(self.scope),
            "non_goals": list(self.non_goals),
            "required_outputs": list(self.required_outputs),
            "success_criteria": list(self.success_criteria),
        }
        if self.notes is not None:
            payload["notes"] = self.notes
        if self.allowed_roots is not None:
            payload["allowed_roots"] = list(self.allowed_roots)
        if self.suggested_commands is not None:
            payload["suggested_commands"] = list(self.suggested_commands)
        if self.verification_commands is not None:
            payload["verification_commands"] = list(self.verification_commands)
        if self.implementation_record_path is not None:
            payload["implementation_record_path"] = self.implementation_record_path
        return payload


@dataclass(slots=True)
class TaskSpecLoadResult:
    status: str
    project_root: Path
    task_path: Path
    task_id: str | None = None
    checks: list[TaskSpecCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    parsed_task: NormalizedTaskSpec | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": str(self.project_root),
            "task_path": str(self.task_path),
            "task_id": self.task_id,
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "parsed_task": self.parsed_task.to_dict() if self.parsed_task is not None else None,
        }


def load_task_spec(project_root: Path, task: str) -> TaskSpecLoadResult:
    project_root = project_root.expanduser().resolve()
    task_path = _resolve_task_path(project_root, task)
    result = TaskSpecLoadResult(
        status="failure",
        project_root=project_root,
        task_path=task_path,
    )

    if not task_path.is_file():
        message = f"Missing task spec file: {task_path}"
        result.checks.append(
            TaskSpecCheck(name="task_file_exists", status="fail", message=message)
        )
        result.errors.append(message)
        return result

    result.checks.append(
        TaskSpecCheck(
            name="task_file_exists",
            status="pass",
            message=f"Found task spec file: {task_path}",
        )
    )

    raw_task = _parse_task_yaml(task_path)
    if isinstance(raw_task, str):
        result.checks.append(
            TaskSpecCheck(name="task_yaml_parses", status="fail", message=raw_task)
        )
        result.errors.append(raw_task)
        return result

    result.checks.append(
        TaskSpecCheck(
            name="task_yaml_parses",
            status="pass",
            message="Parsed task spec YAML successfully.",
        )
    )

    if not isinstance(raw_task, dict):
        message = f"Expected YAML mapping in {task_path}, got {type(raw_task).__name__}."
        result.checks.append(
            TaskSpecCheck(name="task_top_level_mapping", status="fail", message=message)
        )
        result.errors.append(message)
        return result

    result.checks.append(
        TaskSpecCheck(
            name="task_top_level_mapping",
            status="pass",
            message="Task spec top-level YAML structure is a mapping.",
        )
    )

    raw_task_id = raw_task.get("task_id")
    if isinstance(raw_task_id, str) and raw_task_id.strip():
        result.task_id = raw_task_id.strip()

    missing_fields = [field_name for field_name in (*REQUIRED_STRING_FIELDS, *REQUIRED_LIST_FIELDS) if field_name not in raw_task]
    if missing_fields:
        message = "Missing required task fields: " + ", ".join(missing_fields)
        result.checks.append(
            TaskSpecCheck(name="required_task_fields_present", status="fail", message=message)
        )
        result.errors.append(message)
        return result

    result.checks.append(
        TaskSpecCheck(
            name="required_task_fields_present",
            status="pass",
            message="Required task fields are present.",
        )
    )

    invalid_string_messages: list[str] = []
    normalized_strings: dict[str, str] = {}
    for field_name in REQUIRED_STRING_FIELDS:
        normalized_value = _normalize_non_empty_string(raw_task.get(field_name))
        if normalized_value is None:
            invalid_string_messages.append(
                f"Field '{field_name}' must be a non-empty string."
            )
            continue
        normalized_strings[field_name] = normalized_value

    if invalid_string_messages:
        message = "Invalid required string fields: " + "; ".join(invalid_string_messages)
        result.checks.append(
            TaskSpecCheck(
                name="required_task_string_fields_valid",
                status="fail",
                message=message,
            )
        )
        result.errors.append(message)
        return result

    result.checks.append(
        TaskSpecCheck(
            name="required_task_string_fields_valid",
            status="pass",
            message="Required string fields are valid.",
        )
    )
    result.task_id = normalized_strings["task_id"]

    invalid_list_messages: list[str] = []
    normalized_lists: dict[str, list[str]] = {}
    for field_name in REQUIRED_LIST_FIELDS:
        normalized_list = _normalize_string_list(raw_task.get(field_name), allow_empty=False)
        if isinstance(normalized_list, str):
            invalid_list_messages.append(f"Field '{field_name}' {normalized_list}")
            continue
        normalized_lists[field_name] = normalized_list

    if invalid_list_messages:
        message = "Invalid required list fields: " + "; ".join(invalid_list_messages)
        result.checks.append(
            TaskSpecCheck(
                name="required_task_list_fields_valid",
                status="fail",
                message=message,
            )
        )
        result.errors.append(message)
        return result

    result.checks.append(
        TaskSpecCheck(
            name="required_task_list_fields_valid",
            status="pass",
            message="Required list fields are valid.",
        )
    )

    optional_string_values: dict[str, str] = {}
    optional_list_values: dict[str, list[str]] = {}
    optional_field_messages: list[str] = []

    for field_name in OPTIONAL_STRING_FIELDS:
        if field_name not in raw_task:
            continue
        normalized_value = _normalize_non_empty_string(raw_task.get(field_name))
        if normalized_value is None:
            optional_field_messages.append(
                f"Field '{field_name}' must be a non-empty string when provided."
            )
            continue
        optional_string_values[field_name] = normalized_value

    for field_name in OPTIONAL_LIST_FIELDS:
        if field_name not in raw_task:
            continue
        normalized_list = _normalize_string_list(raw_task.get(field_name), allow_empty=True)
        if isinstance(normalized_list, str):
            optional_field_messages.append(f"Field '{field_name}' {normalized_list}")
            continue
        optional_list_values[field_name] = normalized_list

    if optional_field_messages:
        message = "Invalid optional task fields: " + "; ".join(optional_field_messages)
        result.checks.append(
            TaskSpecCheck(name="optional_task_fields_valid", status="fail", message=message)
        )
        result.errors.append(message)
        return result

    result.checks.append(
        TaskSpecCheck(
            name="optional_task_fields_valid",
            status="pass",
            message="Optional task fields are valid when provided.",
        )
    )

    result.parsed_task = NormalizedTaskSpec(
        task_id=normalized_strings["task_id"],
        title=normalized_strings["title"],
        goal=normalized_strings["goal"],
        scope=normalized_lists["scope"],
        non_goals=normalized_lists["non_goals"],
        required_outputs=normalized_lists["required_outputs"],
        success_criteria=normalized_lists["success_criteria"],
        notes=optional_string_values.get("notes"),
        allowed_roots=optional_list_values.get("allowed_roots"),
        suggested_commands=optional_list_values.get("suggested_commands"),
        verification_commands=optional_list_values.get("verification_commands"),
        implementation_record_path=optional_string_values.get("implementation_record_path"),
    )
    result.status = "success"
    return result


def format_task_spec_summary(result: TaskSpecLoadResult) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")

    lines = [
        f"load-task-spec: {result.status.upper()}",
        f"project root: {result.project_root}",
        f"task path: {result.task_path}",
        f"task id: {result.task_id if result.task_id is not None else 'none'}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
    ]

    if failed:
        lines.append("failures:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")
    else:
        lines.append("summary: task spec is valid and ready for bounded handoff.")

    return "\n".join(lines)


def _resolve_task_path(project_root: Path, task: str) -> Path:
    task_text = task.strip()
    candidate = Path(task_text)
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.suffix in {".yaml", ".yml"} or len(candidate.parts) > 1:
        return (project_root / candidate).resolve()
    return (project_root / ".swarm" / "tasks" / f"{task_text}.yaml").resolve()


def _parse_task_yaml(task_path: Path) -> Any | str:
    try:
        with task_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return f"Failed to parse task spec YAML in {task_path}: {exc}"
    except OSError as exc:
        return f"Failed to read task spec file {task_path}: {exc}"


def _normalize_non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    return normalized


def _normalize_string_list(value: Any, allow_empty: bool) -> list[str] | str:
    if not isinstance(value, list):
        return "must be a list of non-empty strings."
    normalized_items: list[str] = []
    for index, item in enumerate(value):
        normalized_item = _normalize_non_empty_string(item)
        if normalized_item is None:
            return f"contains an invalid entry at index {index}; each item must be a non-empty string."
        normalized_items.append(normalized_item)
    if not allow_empty and not normalized_items:
        return "must be a non-empty list of non-empty strings."
    return normalized_items