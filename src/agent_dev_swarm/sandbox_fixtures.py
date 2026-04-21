from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SANDBOX_ROOT = REPO_ROOT / "sandbox"
DEFAULT_FIXTURES_ROOT = DEFAULT_SANDBOX_ROOT / "fixtures"
DEFAULT_RUNS_ROOT = DEFAULT_SANDBOX_ROOT / "runs"
FIXTURE_MANIFEST_NAME = "fixture.yaml"
SANDBOX_LAYOUT_VERSION = "1"
ARTIFACT_DIRECTORIES = (
    "task-input",
    "policy-input",
    "handoff",
    "commands",
    "worker-result",
    "adjudication",
    "implementation-record",
    "summary",
)

REQUIRED_STRING_FIELDS = (
    "fixture_id",
    "description",
    "layout_version",
    "source_root",
    "intended_outcome",
)
REQUIRED_LIST_FIELDS = (
    "materialized_paths",
    "editable_paths",
    "read_only_paths",
    "generated_paths",
)
OPTIONAL_STRING_FIELDS = ("default_task_spec", "default_policy")

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(slots=True)
class SandboxCheck:
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
class SandboxFixtureManifest:
    fixture_id: str
    description: str
    layout_version: str
    source_root: str
    materialized_paths: list[str]
    editable_paths: list[str]
    read_only_paths: list[str]
    generated_paths: list[str]
    intended_outcome: str
    default_task_spec: str | None = None
    default_policy: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fixture_id": self.fixture_id,
            "description": self.description,
            "layout_version": self.layout_version,
            "source_root": self.source_root,
            "materialized_paths": list(self.materialized_paths),
            "editable_paths": list(self.editable_paths),
            "read_only_paths": list(self.read_only_paths),
            "generated_paths": list(self.generated_paths),
            "intended_outcome": self.intended_outcome,
        }
        if self.default_task_spec is not None:
            payload["default_task_spec"] = self.default_task_spec
        if self.default_policy is not None:
            payload["default_policy"] = self.default_policy
        return payload


@dataclass(slots=True)
class SandboxMaterializationResult:
    status: str
    fixture_name: str
    run_id: str
    fixture_root: Path
    manifest_path: Path
    run_root: Path
    workspace_root: Path
    artifacts_root: Path
    checks: list[SandboxCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reset_performed: bool = False
    created_paths: list[str] = field(default_factory=list)
    manifest: SandboxFixtureManifest | None = None
    metadata_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "fixture_name": self.fixture_name,
            "run_id": self.run_id,
            "fixture_root": str(self.fixture_root),
            "manifest_path": str(self.manifest_path),
            "run_root": str(self.run_root),
            "workspace_root": str(self.workspace_root),
            "artifacts_root": str(self.artifacts_root),
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "reset_performed": self.reset_performed,
            "created_paths": list(self.created_paths),
            "manifest": self.manifest.to_dict() if self.manifest is not None else None,
            "metadata_path": str(self.metadata_path) if self.metadata_path is not None else None,
        }


def materialize_sandbox_run(
    fixture_name: str,
    run_id: str,
    force_reset: bool = False,
    fixtures_root: Path | None = None,
    runs_root: Path | None = None,
) -> SandboxMaterializationResult:
    resolved_fixtures_root = (fixtures_root or DEFAULT_FIXTURES_ROOT).expanduser().resolve()
    resolved_runs_root = (runs_root or DEFAULT_RUNS_ROOT).expanduser().resolve()
    normalized_fixture_name = fixture_name.strip()
    normalized_run_id = run_id.strip()

    fixture_root = resolved_fixtures_root / normalized_fixture_name
    manifest_path = fixture_root / FIXTURE_MANIFEST_NAME
    run_root = resolved_runs_root / normalized_run_id
    workspace_root = run_root / "workspace"
    artifacts_root = run_root / "artifacts"

    result = SandboxMaterializationResult(
        status="failure",
        fixture_name=normalized_fixture_name,
        run_id=normalized_run_id,
        fixture_root=fixture_root,
        manifest_path=manifest_path,
        run_root=run_root,
        workspace_root=workspace_root,
        artifacts_root=artifacts_root,
    )

    for field_name, candidate in (("fixture", normalized_fixture_name), ("run_id", normalized_run_id)):
        if not _is_valid_name(candidate):
            message = (
                f"Sandbox {field_name} must use only letters, numbers, dots, underscores, or hyphens: {candidate!r}"
            )
            result.checks.append(_check(f"{field_name}_valid", "fail", message))
            result.errors.append(message)
            return result
        result.checks.append(
            _check(
                f"{field_name}_valid",
                "pass",
                f"Sandbox {field_name} is valid: {candidate}",
            )
        )

    if not fixture_root.is_dir():
        message = f"Missing sandbox fixture directory: {fixture_root}"
        result.checks.append(_check("fixture_directory_exists", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("fixture_directory_exists", "pass", f"Found sandbox fixture directory: {fixture_root}")
    )

    if not manifest_path.is_file():
        message = f"Missing sandbox fixture manifest: {manifest_path}"
        result.checks.append(_check("fixture_manifest_exists", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("fixture_manifest_exists", "pass", f"Found sandbox fixture manifest: {manifest_path}")
    )

    raw_manifest = _parse_manifest_yaml(manifest_path)
    if isinstance(raw_manifest, str):
        result.checks.append(_check("fixture_manifest_parses", "fail", raw_manifest))
        result.errors.append(raw_manifest)
        return result

    result.checks.append(
        _check("fixture_manifest_parses", "pass", "Parsed sandbox fixture manifest YAML successfully.")
    )

    if not isinstance(raw_manifest, dict):
        message = (
            f"Expected sandbox fixture manifest to be a YAML mapping in {manifest_path}, "
            f"got {type(raw_manifest).__name__}."
        )
        result.checks.append(_check("fixture_manifest_top_level_mapping", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check(
            "fixture_manifest_top_level_mapping",
            "pass",
            "Sandbox fixture manifest top-level YAML structure is a mapping.",
        )
    )

    manifest = _build_manifest(fixture_root=fixture_root, manifest_path=manifest_path, raw_manifest=raw_manifest)
    if isinstance(manifest, str):
        result.checks.append(_check("fixture_manifest_fields_valid", "fail", manifest))
        result.errors.append(manifest)
        return result

    result.manifest = manifest
    result.checks.append(
        _check("fixture_manifest_fields_valid", "pass", "Sandbox fixture manifest fields are valid.")
    )

    if run_root.exists() and not force_reset:
        message = (
            f"Sandbox run directory already exists and reset was not requested: {run_root}"
        )
        result.checks.append(_check("run_root_ready", "fail", message))
        result.errors.append(message)
        return result

    if run_root.exists() and force_reset:
        shutil.rmtree(run_root)
        result.reset_performed = True
        result.checks.append(
            _check("run_root_reset", "pass", f"Removed existing sandbox run directory: {run_root}")
        )

    resolved_runs_root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    result.created_paths.extend([str(run_root), str(workspace_root), str(artifacts_root)])
    result.checks.append(
        _check("run_root_ready", "pass", f"Sandbox run root is ready: {run_root}")
    )

    for artifact_dir in ARTIFACT_DIRECTORIES:
        created_dir = artifacts_root / artifact_dir
        created_dir.mkdir(parents=True, exist_ok=True)
        result.created_paths.append(str(created_dir))

    for relative_path in manifest.materialized_paths:
        source_path = (fixture_root / manifest.source_root / relative_path).resolve()
        destination_path = (workspace_root / relative_path).resolve()
        if destination_path.exists():
            continue
        _copy_path(source_path, destination_path)
        result.created_paths.append(str(destination_path))

    for generated_path in manifest.generated_paths:
        created_dir = (workspace_root / generated_path).resolve()
        created_dir.mkdir(parents=True, exist_ok=True)
        result.created_paths.append(str(created_dir))

    metadata_path = run_root / "run-info.json"
    metadata_path.write_text(
        json.dumps(
            {
                "fixture_name": normalized_fixture_name,
                "run_id": normalized_run_id,
                "run_root": str(run_root),
                "workspace_root": str(workspace_root),
                "artifacts_root": str(artifacts_root),
                "manifest_path": str(manifest_path),
                "manifest": manifest.to_dict(),
                "artifact_directories": [str(artifacts_root / name) for name in ARTIFACT_DIRECTORIES],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result.metadata_path = metadata_path
    result.created_paths.append(str(metadata_path))
    result.checks.append(
        _check(
            "run_metadata_written",
            "pass",
            f"Wrote sandbox run metadata: {metadata_path}",
        )
    )

    result.status = "success"
    return result


def format_sandbox_materialization_summary(result: SandboxMaterializationResult) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")

    lines = [
        f"materialize-sandbox-run: {result.status.upper()}",
        f"fixture: {result.fixture_name}",
        f"run id: {result.run_id}",
        f"run root: {result.run_root}",
        f"workspace root: {result.workspace_root}",
        f"artifacts root: {result.artifacts_root}",
        f"reset performed: {'yes' if result.reset_performed else 'no'}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
    ]

    if failed:
        lines.append("failures:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")
    else:
        lines.append("summary: sandbox run workspace and artifact scaffold were materialized successfully.")

    return "\n".join(lines)


def _build_manifest(
    fixture_root: Path,
    manifest_path: Path,
    raw_manifest: dict[str, Any],
) -> SandboxFixtureManifest | str:
    missing_fields = [
        field_name
        for field_name in (*REQUIRED_STRING_FIELDS, *REQUIRED_LIST_FIELDS)
        if field_name not in raw_manifest
    ]
    if missing_fields:
        return "Missing required sandbox fixture fields: " + ", ".join(missing_fields)

    normalized_strings: dict[str, str] = {}
    string_errors: list[str] = []
    for field_name in REQUIRED_STRING_FIELDS:
        normalized_value = _normalize_non_empty_string(raw_manifest.get(field_name))
        if normalized_value is None:
            string_errors.append(f"Field '{field_name}' must be a non-empty string.")
            continue
        normalized_strings[field_name] = normalized_value

    optional_strings: dict[str, str] = {}
    for field_name in OPTIONAL_STRING_FIELDS:
        if field_name not in raw_manifest:
            continue
        normalized_value = _normalize_non_empty_string(raw_manifest.get(field_name))
        if normalized_value is None:
            string_errors.append(f"Field '{field_name}' must be a non-empty string when provided.")
            continue
        optional_strings[field_name] = normalized_value

    if string_errors:
        return "Invalid sandbox fixture string fields: " + "; ".join(string_errors)

    if normalized_strings["layout_version"] != SANDBOX_LAYOUT_VERSION:
        return (
            f"Unsupported sandbox fixture layout_version '{normalized_strings['layout_version']}'. "
            f"Expected {SANDBOX_LAYOUT_VERSION}."
        )

    source_root_text = normalized_strings["source_root"]
    source_root_path = (fixture_root / source_root_text).resolve()
    if not source_root_path.is_dir():
        return f"Sandbox fixture source_root does not exist as a directory: {source_root_path}"

    normalized_lists: dict[str, list[str]] = {}
    list_errors: list[str] = []
    for field_name in REQUIRED_LIST_FIELDS:
        normalized_list = _normalize_relative_string_list(
            raw_manifest.get(field_name),
            allow_empty=(field_name != "materialized_paths"),
        )
        if isinstance(normalized_list, str):
            list_errors.append(f"Field '{field_name}' {normalized_list}")
            continue
        normalized_lists[field_name] = normalized_list

    if list_errors:
        return "Invalid sandbox fixture list fields: " + "; ".join(list_errors)

    for relative_path in normalized_lists["materialized_paths"]:
        materialized_source = (source_root_path / relative_path).resolve()
        if not _is_relative_to(materialized_source, source_root_path):
            return (
                f"Field 'materialized_paths' contains a path that escapes the source root: {relative_path}"
            )
        if not materialized_source.exists():
            return (
                f"Field 'materialized_paths' references missing fixture content: {materialized_source}"
            )

    for field_name in ("default_task_spec", "default_policy"):
        if field_name not in optional_strings:
            continue
        referenced_path = (source_root_path / optional_strings[field_name]).resolve()
        if not _is_relative_to(referenced_path, source_root_path):
            return f"Field '{field_name}' escapes the sandbox fixture source root: {optional_strings[field_name]}"
        if not referenced_path.exists():
            return f"Field '{field_name}' references missing fixture content: {referenced_path}"

    return SandboxFixtureManifest(
        fixture_id=normalized_strings["fixture_id"],
        description=normalized_strings["description"],
        layout_version=normalized_strings["layout_version"],
        source_root=source_root_text,
        materialized_paths=normalized_lists["materialized_paths"],
        editable_paths=normalized_lists["editable_paths"],
        read_only_paths=normalized_lists["read_only_paths"],
        generated_paths=normalized_lists["generated_paths"],
        intended_outcome=normalized_strings["intended_outcome"],
        default_task_spec=optional_strings.get("default_task_spec"),
        default_policy=optional_strings.get("default_policy"),
    )


def _parse_manifest_yaml(manifest_path: Path) -> Any | str:
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return f"Failed to parse sandbox fixture YAML in {manifest_path}: {exc}"
    except OSError as exc:
        return f"Failed to read sandbox fixture manifest {manifest_path}: {exc}"


def _normalize_non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    return normalized


def _normalize_relative_string_list(value: Any, allow_empty: bool) -> list[str] | str:
    if not isinstance(value, list):
        return "must be a list of relative non-empty strings."

    normalized_items: list[str] = []
    for index, item in enumerate(value):
        normalized_item = _normalize_non_empty_string(item)
        if normalized_item is None:
            return f"contains an invalid entry at index {index}; each item must be a non-empty string."
        candidate_path = Path(normalized_item)
        if candidate_path.is_absolute() or any(part == ".." for part in candidate_path.parts):
            return f"contains an invalid relative path at index {index}: {normalized_item!r}."
        normalized_items.append(normalized_item)

    if not allow_empty and not normalized_items:
        return "must be a non-empty list of relative non-empty strings."

    return normalized_items


def _is_valid_name(value: str) -> bool:
    return bool(value) and NAME_PATTERN.fullmatch(value) is not None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _copy_path(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.is_dir():
        shutil.copytree(source_path, destination_path)
        return
    shutil.copy2(source_path, destination_path)


def _check(name: str, status: str, message: str) -> SandboxCheck:
    return SandboxCheck(name=name, status=status, message=message)