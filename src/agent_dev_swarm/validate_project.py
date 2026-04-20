from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FIELDS = ("project_name", "framework_checkout")
DOC_PATH_FIELDS = (
    "rules_doc",
    "artifact_spec_doc",
    "framework_architecture_doc",
    "bootstrap_plan_doc",
)


@dataclass(slots=True)
class CheckResult:
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
class ValidationResult:
    status: str
    project_root: Path
    config_path: Path
    checks: list[CheckResult] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    parsed_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": str(self.project_root),
            "config_path": str(self.config_path),
            "checks": [check.to_dict() for check in self.checks],
            "missing_items": list(self.missing_items),
            "errors": list(self.errors),
        }


def validate_project(project_root: Path) -> ValidationResult:
    project_root = project_root.expanduser().resolve()
    config_path = project_root / ".swarm" / "project.yaml"
    result = ValidationResult(
        status="failure",
        project_root=project_root,
        config_path=config_path,
    )

    if not config_path.is_file():
        result.checks.append(
            CheckResult(
                name="project_config_exists",
                status="fail",
                message=f"Missing project config: {config_path}",
            )
        )
        result.missing_items.append(str(config_path))
        result.errors.append("Project config file .swarm/project.yaml was not found.")
        return result

    result.checks.append(
        CheckResult(
            name="project_config_exists",
            status="pass",
            message=f"Found project config: {config_path}",
        )
    )

    parsed_config = _parse_config(config_path)
    if isinstance(parsed_config, str):
        result.checks.append(
            CheckResult(
                name="project_config_parses",
                status="fail",
                message=parsed_config,
            )
        )
        result.errors.append(parsed_config)
        return result

    result.parsed_config = parsed_config
    result.checks.append(
        CheckResult(
            name="project_config_parses",
            status="pass",
            message="Parsed .swarm/project.yaml successfully.",
        )
    )

    missing_fields = [field for field in REQUIRED_FIELDS if not _has_value(parsed_config.get(field))]
    if missing_fields:
        message = "Missing required YAML fields: " + ", ".join(missing_fields)
        result.checks.append(
            CheckResult(
                name="required_yaml_fields_present",
                status="fail",
                message=message,
            )
        )
        result.missing_items.extend(missing_fields)
        result.errors.append(message)
        return result

    result.checks.append(
        CheckResult(
            name="required_yaml_fields_present",
            status="pass",
            message="Required YAML fields are present.",
        )
    )

    framework_checkout = project_root / str(parsed_config["framework_checkout"])
    if not framework_checkout.exists():
        message = f"Configured framework checkout does not exist: {framework_checkout}"
        result.checks.append(
            CheckResult(
                name="framework_checkout_exists",
                status="fail",
                message=message,
            )
        )
        result.missing_items.append(str(framework_checkout))
        result.errors.append(message)
        return result

    result.checks.append(
        CheckResult(
            name="framework_checkout_exists",
            status="pass",
            message=f"Framework checkout exists: {framework_checkout}",
        )
    )

    missing_docs: list[str] = []
    for field in DOC_PATH_FIELDS:
        configured_path = parsed_config.get(field)
        if not _has_value(configured_path):
            continue

        doc_path = project_root / str(configured_path)
        if doc_path.is_file():
            result.checks.append(
                CheckResult(
                    name=f"referenced_doc_exists:{field}",
                    status="pass",
                    message=f"Referenced doc exists for {field}: {doc_path}",
                )
            )
            continue

        result.checks.append(
            CheckResult(
                name=f"referenced_doc_exists:{field}",
                status="fail",
                message=f"Referenced doc for {field} does not exist: {doc_path}",
            )
        )
        missing_docs.append(f"{field} -> {doc_path}")

    if missing_docs:
        result.missing_items.extend(missing_docs)
        result.errors.append("Missing referenced docs: " + "; ".join(missing_docs))
        return result

    result.status = "success"
    return result


def format_terminal_summary(result: ValidationResult) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")

    lines = [
        f"validate-project: {result.status.upper()}",
        f"project root: {result.project_root}",
        f"config path: {result.config_path}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
    ]

    if failed:
        lines.append("failures:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")
    else:
        lines.append("summary: project attachment is valid.")

    return "\n".join(lines)


def _parse_config(config_path: Path) -> dict[str, Any] | str:
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return f"Failed to parse YAML in {config_path}: {exc}"
    except OSError as exc:
        return f"Failed to read {config_path}: {exc}"

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        return f"Expected YAML mapping in {config_path}, got {type(loaded).__name__}."
    return loaded


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True