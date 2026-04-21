from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_dev_swarm.handoff_adjudication import build_worker_handoff
from agent_dev_swarm.sandbox_fixtures import DEFAULT_RUNS_ROOT
from agent_dev_swarm.task_specs import load_task_spec

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(slots=True)
class SupervisedRunCheck:
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
class SupervisedRunResult:
    status: str
    run_id: str
    run_root: Path
    workspace_root: Path
    artifacts_root: Path
    worker_role: str
    task_path: Path | None = None
    policy_path: Path | None = None
    handoff_path: Path | None = None
    worker_result_starter_path: Path | None = None
    run_plan_path: Path | None = None
    checks: list[SupervisedRunCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_paths: list[str] = field(default_factory=list)
    overwritten_paths: list[str] = field(default_factory=list)
    task_source: str | None = None
    policy_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_id": self.run_id,
            "run_root": str(self.run_root),
            "workspace_root": str(self.workspace_root),
            "artifacts_root": str(self.artifacts_root),
            "worker_role": self.worker_role,
            "task_path": str(self.task_path) if self.task_path is not None else None,
            "policy_path": str(self.policy_path) if self.policy_path is not None else None,
            "handoff_path": str(self.handoff_path) if self.handoff_path is not None else None,
            "worker_result_starter_path": (
                str(self.worker_result_starter_path)
                if self.worker_result_starter_path is not None
                else None
            ),
            "run_plan_path": str(self.run_plan_path) if self.run_plan_path is not None else None,
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "created_paths": list(self.created_paths),
            "overwritten_paths": list(self.overwritten_paths),
            "task_source": self.task_source,
            "policy_source": self.policy_source,
        }


def scaffold_supervised_run(
    run_id: str,
    worker_role: str,
    task: str | None = None,
    policy: str | None = None,
    force_overwrite: bool = False,
    runs_root: Path | None = None,
) -> SupervisedRunResult:
    resolved_runs_root = (runs_root or DEFAULT_RUNS_ROOT).expanduser().resolve()
    normalized_run_id = run_id.strip()
    normalized_worker_role = worker_role.strip()
    run_root = resolved_runs_root / normalized_run_id
    workspace_root = run_root / "workspace"
    artifacts_root = run_root / "artifacts"

    result = SupervisedRunResult(
        status="failure",
        run_id=normalized_run_id,
        run_root=run_root,
        workspace_root=workspace_root,
        artifacts_root=artifacts_root,
        worker_role=normalized_worker_role,
    )

    if RUN_ID_PATTERN.fullmatch(normalized_run_id) is None:
        message = (
            f"Run id must use only letters, numbers, dots, underscores, or hyphens: {normalized_run_id!r}"
        )
        result.checks.append(_check("run_id_valid", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("run_id_valid", "pass", f"Run id is valid: {normalized_run_id}")
    )

    if not normalized_worker_role:
        message = "Worker role must be a non-empty string."
        result.checks.append(_check("worker_role_valid", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("worker_role_valid", "pass", f"Worker role is valid: {normalized_worker_role}")
    )

    if not run_root.is_dir():
        message = f"Missing sandbox run directory: {run_root}"
        result.checks.append(_check("run_root_exists", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("run_root_exists", "pass", f"Found sandbox run directory: {run_root}")
    )

    metadata_path = run_root / "run-info.json"
    if not metadata_path.is_file():
        message = f"Missing sandbox run metadata file: {metadata_path}"
        result.checks.append(_check("run_metadata_exists", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("run_metadata_exists", "pass", f"Found sandbox run metadata file: {metadata_path}")
    )

    metadata = _load_json_file(metadata_path)
    if isinstance(metadata, str):
        result.checks.append(_check("run_metadata_parses", "fail", metadata))
        result.errors.append(metadata)
        return result

    result.checks.append(
        _check("run_metadata_parses", "pass", "Parsed sandbox run metadata successfully.")
    )

    if not isinstance(metadata, dict):
        message = f"Expected JSON object in sandbox run metadata: {metadata_path}"
        result.checks.append(_check("run_metadata_shape_valid", "fail", message))
        result.errors.append(message)
        return result

    metadata_workspace_root = _normalize_non_empty_string(metadata.get("workspace_root"))
    metadata_artifacts_root = _normalize_non_empty_string(metadata.get("artifacts_root"))
    manifest = metadata.get("manifest")
    if metadata_workspace_root is None or metadata_artifacts_root is None or not isinstance(manifest, dict):
        message = (
            f"Sandbox run metadata is missing required workspace_root, artifacts_root, or manifest fields: {metadata_path}"
        )
        result.checks.append(_check("run_metadata_shape_valid", "fail", message))
        result.errors.append(message)
        return result

    result.workspace_root = Path(metadata_workspace_root).expanduser().resolve()
    result.artifacts_root = Path(metadata_artifacts_root).expanduser().resolve()
    result.checks.append(
        _check("run_metadata_shape_valid", "pass", "Sandbox run metadata contains the required fields.")
    )

    if not result.workspace_root.is_dir():
        message = f"Missing sandbox workspace directory: {result.workspace_root}"
        result.checks.append(_check("workspace_root_exists", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("workspace_root_exists", "pass", f"Found sandbox workspace directory: {result.workspace_root}")
    )

    if not result.artifacts_root.is_dir():
        message = f"Missing sandbox artifacts directory: {result.artifacts_root}"
        result.checks.append(_check("artifacts_root_exists", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("artifacts_root_exists", "pass", f"Found sandbox artifacts directory: {result.artifacts_root}")
    )

    task_path, task_source = _resolve_task_path(result.workspace_root, manifest, task)
    result.task_source = task_source
    if isinstance(task_path, str):
        result.checks.append(_check("task_path_resolved", "fail", task_path))
        result.errors.append(task_path)
        return result

    result.task_path = task_path
    result.checks.append(
        _check("task_path_resolved", "pass", f"Resolved task spec path: {task_path}")
    )

    policy_path, policy_source = _resolve_policy_path(result.workspace_root, manifest, policy)
    result.policy_source = policy_source
    if isinstance(policy_path, str):
        result.checks.append(_check("policy_path_resolved", "fail", policy_path))
        result.errors.append(policy_path)
        return result
    if policy_path is not None:
        result.policy_path = policy_path
        result.checks.append(
            _check("policy_path_resolved", "pass", f"Resolved policy path: {policy_path}")
        )
    else:
        result.checks.append(
            _check("policy_path_resolved", "pass", "No policy reference was provided or available by default.")
        )

    task_result = load_task_spec(result.workspace_root, str(result.task_path))
    result.checks.extend(
        _check(check.name, check.status, check.message) for check in task_result.checks
    )
    if task_result.status != "success" or task_result.parsed_task is None:
        result.errors.extend(task_result.errors)
        return result

    handoff_result = build_worker_handoff(
        project_root=result.workspace_root,
        task=str(result.task_path),
        worker_role=normalized_worker_role,
        policy_reference=_relative_to_workspace(result.policy_path, result.workspace_root)
        if result.policy_path is not None
        else None,
    )
    result.checks.extend(handoff_result.checks)
    if handoff_result.status != "success" or handoff_result.handoff is None:
        result.errors.extend(handoff_result.errors)
        return result

    task_input_path = result.artifacts_root / "task-input" / "task-spec.json"
    policy_input_path = result.artifacts_root / "policy-input" / "policy-reference.json"
    handoff_path = result.artifacts_root / "handoff" / "worker-handoff.json"
    worker_result_starter_path = result.artifacts_root / "worker-result" / "worker-result-starter.json"
    run_plan_path = result.artifacts_root / "summary" / "run-plan.json"

    artifact_paths = [
        task_input_path,
        policy_input_path,
        handoff_path,
        worker_result_starter_path,
        run_plan_path,
    ]
    existing_artifacts = [path for path in artifact_paths if path.exists()]
    if existing_artifacts and not force_overwrite:
        message = (
            "Supervised run artifacts already exist and overwrite was not requested: "
            + ", ".join(str(path) for path in existing_artifacts)
        )
        result.checks.append(_check("artifact_paths_writable", "fail", message))
        result.errors.append(message)
        return result

    if existing_artifacts:
        result.overwritten_paths.extend(str(path) for path in existing_artifacts)
        result.checks.append(
            _check(
                "artifact_paths_writable",
                "pass",
                "Existing supervised-run artifacts will be overwritten explicitly.",
            )
        )
    else:
        result.checks.append(
            _check(
                "artifact_paths_writable",
                "pass",
                "Supervised-run artifact paths are available for creation.",
            )
        )

    task_artifact = {
        "task_path": str(result.task_path),
        "task_source": result.task_source,
        "task_spec": task_result.parsed_task.to_dict(),
    }
    policy_artifact = {
        "policy_path": str(result.policy_path) if result.policy_path is not None else None,
        "policy_source": result.policy_source,
        "policy_present": result.policy_path is not None,
    }
    worker_result_starter = _build_worker_result_starter(handoff_result.handoff)
    run_plan = {
        "run_id": result.run_id,
        "run_root": str(result.run_root),
        "workspace_root": str(result.workspace_root),
        "artifacts_root": str(result.artifacts_root),
        "worker_role": result.worker_role,
        "task_path": str(result.task_path),
        "task_source": result.task_source,
        "policy_path": str(result.policy_path) if result.policy_path is not None else None,
        "policy_source": result.policy_source,
        "fixture_name": _normalize_non_empty_string(metadata.get("fixture_name")),
        "default_task_spec": _normalize_non_empty_string(manifest.get("default_task_spec")),
        "default_policy": _normalize_non_empty_string(manifest.get("default_policy")),
        "handoff_path": str(handoff_path),
        "worker_result_starter_path": str(worker_result_starter_path),
        "task_input_path": str(task_input_path),
        "policy_input_path": str(policy_input_path),
        "next_expected_steps": [
            "Inspect the worker handoff payload.",
            "Attempt the bounded work inside the sandbox workspace.",
            "Fill in the worker-result starter artifact.",
            "Adjudicate the completed worker result with the existing command.",
        ],
    }

    _write_json(task_input_path, task_artifact)
    _write_json(policy_input_path, policy_artifact)
    _write_json(handoff_path, handoff_result.handoff.to_dict())
    _write_json(worker_result_starter_path, worker_result_starter)
    _write_json(run_plan_path, run_plan)

    result.created_paths.extend(
        [
            str(task_input_path),
            str(policy_input_path),
            str(handoff_path),
            str(worker_result_starter_path),
            str(run_plan_path),
        ]
    )
    result.handoff_path = handoff_path
    result.worker_result_starter_path = worker_result_starter_path
    result.run_plan_path = run_plan_path
    result.status = "success"
    result.checks.append(
        _check("supervised_run_artifacts_written", "pass", "Wrote supervised run artifact scaffold successfully.")
    )
    return result


def format_supervised_run_summary(result: SupervisedRunResult) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")

    lines = [
        f"scaffold-supervised-run: {result.status.upper()}",
        f"run id: {result.run_id}",
        f"run root: {result.run_root}",
        f"workspace root: {result.workspace_root}",
        f"task path: {result.task_path if result.task_path is not None else 'none'}",
        f"policy path: {result.policy_path if result.policy_path is not None else 'none'}",
        f"worker role: {result.worker_role}",
        f"handoff path: {result.handoff_path if result.handoff_path is not None else 'none'}",
        (
            "worker-result starter path: "
            f"{result.worker_result_starter_path if result.worker_result_starter_path is not None else 'none'}"
        ),
        f"run plan path: {result.run_plan_path if result.run_plan_path is not None else 'none'}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
    ]

    if failed:
        lines.append("failures:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")
    else:
        lines.append("summary: supervised run scaffold is ready for a bounded worker attempt.")

    return "\n".join(lines)


def _resolve_task_path(
    workspace_root: Path,
    manifest: dict[str, Any],
    task_override: str | None,
) -> tuple[Path | None, str | None] | tuple[str, str | None]:
    if task_override is not None:
        task_text = task_override.strip()
        if not task_text:
            return "Task override must be a non-empty string when provided.", "override"
        candidate = Path(task_text)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        elif candidate.suffix in {".yaml", ".yml"} or len(candidate.parts) > 1:
            resolved = (workspace_root / candidate).resolve()
        else:
            resolved = (workspace_root / ".swarm" / "tasks" / f"{task_text}.yaml").resolve()
        if not resolved.is_file():
            return f"Resolved task spec file does not exist: {resolved}", "override"
        return resolved, "override"

    default_task_spec = _normalize_non_empty_string(manifest.get("default_task_spec"))
    if default_task_spec is None:
        return "No task override was provided and the sandbox fixture does not define default_task_spec.", None

    resolved = (workspace_root / default_task_spec).resolve()
    if not _is_relative_to(resolved, workspace_root):
        return f"Default task spec escapes the sandbox workspace: {default_task_spec}", "manifest_default"
    if not resolved.is_file():
        return f"Missing default task spec file in the sandbox workspace: {resolved}", "manifest_default"
    return resolved, "manifest_default"


def _resolve_policy_path(
    workspace_root: Path,
    manifest: dict[str, Any],
    policy_override: str | None,
) -> tuple[Path | None, str | None] | tuple[str, str | None]:
    if policy_override is not None:
        policy_text = policy_override.strip()
        if not policy_text:
            return "Policy override must be a non-empty string when provided.", "override"
        candidate = Path(policy_text)
        resolved = candidate.resolve() if candidate.is_absolute() else (workspace_root / candidate).resolve()
        if not resolved.is_file():
            return f"Resolved policy file does not exist: {resolved}", "override"
        return resolved, "override"

    default_policy = _normalize_non_empty_string(manifest.get("default_policy"))
    if default_policy is None:
        return None, None

    resolved = (workspace_root / default_policy).resolve()
    if not _is_relative_to(resolved, workspace_root):
        return f"Default policy path escapes the sandbox workspace: {default_policy}", "manifest_default"
    if not resolved.is_file():
        return f"Missing default policy file in the sandbox workspace: {resolved}", "manifest_default"
    return resolved, "manifest_default"


def _build_worker_result_starter(handoff: Any) -> dict[str, Any]:
    return {
        "task_id": handoff.task_id,
        "worker_role": handoff.worker_role,
        "status": "partial",
        "summary": "TODO: summarize the bounded work attempt and outcome.",
        "actions_performed": [],
        "files_read": [],
        "files_changed": [],
        "commands_run": [],
        "command_results": [],
        "verification_status": "not_run",
        "required_outputs_status": [
            {"name": item_name, "status": "not_evaluated"}
            for item_name in handoff.required_outputs
        ],
        "success_criteria_status": [
            {"name": item_name, "status": "not_evaluated"}
            for item_name in handoff.success_criteria
        ],
        "unresolved_issues": [],
        "escalation_notes": [],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_json_file(path: Path) -> dict[str, Any] | list[Any] | str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        return f"Failed to parse JSON file {path}: {exc}"
    except OSError as exc:
        return f"Failed to read JSON file {path}: {exc}"


def _normalize_non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    return normalized


def _relative_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _check(name: str, status: str, message: str) -> SupervisedRunCheck:
    return SupervisedRunCheck(name=name, status=status, message=message)