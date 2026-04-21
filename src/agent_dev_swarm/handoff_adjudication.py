from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_dev_swarm.task_specs import NormalizedTaskSpec, load_task_spec

HANDOFF_VERSION = "1"
WORKER_RESULT_STATUSES = ("success", "failure", "partial", "blocked")
VERIFICATION_STATUSES = ("not_run", "passed", "failed", "mixed")
COMMAND_OUTCOMES = ("success", "failure", "refused", "timeout", "not_run")
ITEM_STATUS_VALUES = ("satisfied", "missing", "partial", "not_evaluated")
ADJUDICATION_DECISIONS = ("accept", "reject", "retry", "escalate")

EXPECTED_RESULT_FIELDS = (
    "task_id",
    "worker_role",
    "status",
    "summary",
    "actions_performed",
    "files_read",
    "files_changed",
    "commands_run",
    "command_results",
    "verification_status",
    "required_outputs_status",
    "success_criteria_status",
    "unresolved_issues",
    "escalation_notes",
)


@dataclass(slots=True)
class ControlLoopCheck:
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
class WorkerHandoffPayload:
    task_id: str
    title: str
    goal: str
    scope: list[str]
    non_goals: list[str]
    required_outputs: list[str]
    success_criteria: list[str]
    project_root: str
    worker_role: str
    expected_result_fields: list[str]
    handoff_version: str = HANDOFF_VERSION
    notes: str | None = None
    allowed_roots: list[str] | None = None
    suggested_commands: list[str] | None = None
    verification_commands: list[str] | None = None
    implementation_record_path: str | None = None
    policy_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "handoff_version": self.handoff_version,
            "task_id": self.task_id,
            "title": self.title,
            "goal": self.goal,
            "scope": list(self.scope),
            "non_goals": list(self.non_goals),
            "required_outputs": list(self.required_outputs),
            "success_criteria": list(self.success_criteria),
            "project_root": self.project_root,
            "worker_role": self.worker_role,
            "expected_result_fields": list(self.expected_result_fields),
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
        if self.policy_reference is not None:
            payload["policy_reference"] = self.policy_reference
        return payload


@dataclass(slots=True)
class WorkerHandoffBuildResult:
    status: str
    project_root: Path
    task_path: Path
    worker_role: str
    task_id: str | None = None
    checks: list[ControlLoopCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    handoff: WorkerHandoffPayload | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": str(self.project_root),
            "task_path": str(self.task_path),
            "worker_role": self.worker_role,
            "task_id": self.task_id,
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "handoff": self.handoff.to_dict() if self.handoff is not None else None,
        }


@dataclass(slots=True)
class CommandResultEntry:
    command: str
    outcome: str
    exit_code: int | None = None
    summary: str | None = None
    evidence_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "command": self.command,
            "outcome": self.outcome,
        }
        if self.exit_code is not None:
            payload["exit_code"] = self.exit_code
        if self.summary is not None:
            payload["summary"] = self.summary
        if self.evidence_ref is not None:
            payload["evidence_ref"] = self.evidence_ref
        return payload


@dataclass(slots=True)
class ItemStatusEntry:
    name: str
    status: str
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


@dataclass(slots=True)
class NormalizedWorkerResult:
    task_id: str
    worker_role: str
    status: str
    summary: str
    actions_performed: list[str]
    files_read: list[str]
    files_changed: list[str]
    commands_run: list[str]
    command_results: list[CommandResultEntry]
    verification_status: str
    required_outputs_status: list[ItemStatusEntry]
    success_criteria_status: list[ItemStatusEntry]
    unresolved_issues: list[str]
    escalation_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "worker_role": self.worker_role,
            "status": self.status,
            "summary": self.summary,
            "actions_performed": list(self.actions_performed),
            "files_read": list(self.files_read),
            "files_changed": list(self.files_changed),
            "commands_run": list(self.commands_run),
            "command_results": [item.to_dict() for item in self.command_results],
            "verification_status": self.verification_status,
            "required_outputs_status": [item.to_dict() for item in self.required_outputs_status],
            "success_criteria_status": [item.to_dict() for item in self.success_criteria_status],
            "unresolved_issues": list(self.unresolved_issues),
            "escalation_notes": list(self.escalation_notes),
        }


@dataclass(slots=True)
class WorkerResultValidationResult:
    status: str
    input_path: Path | None = None
    task_id: str | None = None
    checks: list[ControlLoopCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    parsed_result: NormalizedWorkerResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "input_path": str(self.input_path) if self.input_path is not None else None,
            "task_id": self.task_id,
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "parsed_result": self.parsed_result.to_dict() if self.parsed_result is not None else None,
        }


@dataclass(slots=True)
class AdjudicationResult:
    task_id: str | None
    decision: str
    reason: str
    status: str
    required_outputs_satisfied: bool
    success_criteria_satisfied: bool
    unresolved_issues_present: bool
    escalation_requested: bool
    next_action: str
    input_path: Path | None = None
    worker_result_status: str | None = None
    checks: list[ControlLoopCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "decision": self.decision,
            "reason": self.reason,
            "status": self.status,
            "required_outputs_satisfied": self.required_outputs_satisfied,
            "success_criteria_satisfied": self.success_criteria_satisfied,
            "unresolved_issues_present": self.unresolved_issues_present,
            "escalation_requested": self.escalation_requested,
            "next_action": self.next_action,
            "input_path": str(self.input_path) if self.input_path is not None else None,
            "worker_result_status": self.worker_result_status,
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
        }


def build_worker_handoff(
    project_root: Path,
    task: str,
    worker_role: str,
    policy_reference: str | None = None,
) -> WorkerHandoffBuildResult:
    project_root = project_root.expanduser().resolve()
    task_result = load_task_spec(project_root=project_root, task=task)
    result = WorkerHandoffBuildResult(
        status="failure",
        project_root=project_root,
        task_path=task_result.task_path,
        worker_role=worker_role.strip(),
        task_id=task_result.task_id,
        checks=[_coerce_check(check.name, check.status, check.message) for check in task_result.checks],
        errors=list(task_result.errors),
    )

    if task_result.status != "success" or task_result.parsed_task is None:
        result.checks.append(
            _coerce_check(
                "task_spec_valid",
                "fail",
                "Worker handoff cannot be built because the task spec is invalid.",
            )
        )
        return result

    result.checks.append(
        _coerce_check(
            "task_spec_valid",
            "pass",
            f"Task spec is valid for handoff: {task_result.parsed_task.task_id}",
        )
    )

    if not worker_role.strip():
        message = "Worker role must be a non-empty string."
        result.checks.append(_coerce_check("worker_role_valid", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _coerce_check(
            "worker_role_valid",
            "pass",
            f"Worker role is valid: {worker_role.strip()}",
        )
    )

    normalized_policy_reference: str | None = None
    if policy_reference is not None:
        if not policy_reference.strip():
            message = "Policy reference must be a non-empty string when provided."
            result.checks.append(_coerce_check("policy_reference_valid", "fail", message))
            result.errors.append(message)
            return result
        normalized_policy_reference = policy_reference.strip()
        result.checks.append(
            _coerce_check(
                "policy_reference_valid",
                "pass",
                f"Policy reference is valid: {normalized_policy_reference}",
            )
        )

    result.handoff = _build_payload_from_task(
        project_root=project_root,
        task=task_result.parsed_task,
        worker_role=worker_role.strip(),
        policy_reference=normalized_policy_reference,
    )
    result.status = "success"
    result.checks.append(
        _coerce_check(
            "handoff_payload_created",
            "pass",
            f"Built worker handoff payload for task {task_result.parsed_task.task_id}.",
        )
    )
    return result


def validate_worker_result_payload(
    payload: Any,
    input_path: Path | None = None,
) -> WorkerResultValidationResult:
    result = WorkerResultValidationResult(status="failure", input_path=input_path)

    if not isinstance(payload, dict):
        message = (
            f"Expected worker result payload to be a JSON object, got {type(payload).__name__}."
        )
        result.checks.append(_coerce_check("worker_result_top_level_mapping", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _coerce_check(
            "worker_result_top_level_mapping",
            "pass",
            "Worker result top-level JSON structure is an object.",
        )
    )

    raw_task_id = payload.get("task_id")
    if isinstance(raw_task_id, str) and raw_task_id.strip():
        result.task_id = raw_task_id.strip()

    missing_fields = [field_name for field_name in EXPECTED_RESULT_FIELDS if field_name not in payload]
    if missing_fields:
        message = "Missing required worker result fields: " + ", ".join(missing_fields)
        result.checks.append(_coerce_check("worker_result_required_fields_present", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _coerce_check(
            "worker_result_required_fields_present",
            "pass",
            "Required worker result fields are present.",
        )
    )

    normalized_task_id = _normalize_non_empty_string(payload.get("task_id"))
    normalized_worker_role = _normalize_non_empty_string(payload.get("worker_role"))
    normalized_summary = _normalize_non_empty_string(payload.get("summary"))
    raw_status = _normalize_non_empty_string(payload.get("status"))
    raw_verification_status = _normalize_non_empty_string(payload.get("verification_status"))

    invalid_string_messages: list[str] = []
    if normalized_task_id is None:
        invalid_string_messages.append("Field 'task_id' must be a non-empty string.")
    if normalized_worker_role is None:
        invalid_string_messages.append("Field 'worker_role' must be a non-empty string.")
    if normalized_summary is None:
        invalid_string_messages.append("Field 'summary' must be a non-empty string.")
    if raw_status is None:
        invalid_string_messages.append("Field 'status' must be a non-empty string.")
    if raw_verification_status is None:
        invalid_string_messages.append("Field 'verification_status' must be a non-empty string.")

    if invalid_string_messages:
        message = "Invalid worker result string fields: " + "; ".join(invalid_string_messages)
        result.checks.append(_coerce_check("worker_result_string_fields_valid", "fail", message))
        result.errors.append(message)
        return result

    result.task_id = normalized_task_id
    result.checks.append(
        _coerce_check(
            "worker_result_string_fields_valid",
            "pass",
            "Required worker result string fields are valid.",
        )
    )

    if raw_status not in WORKER_RESULT_STATUSES:
        message = "Worker result status must be one of: " + ", ".join(WORKER_RESULT_STATUSES)
        result.checks.append(_coerce_check("worker_result_status_valid", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _coerce_check(
            "worker_result_status_valid",
            "pass",
            f"Worker result status is valid: {raw_status}",
        )
    )

    if raw_verification_status not in VERIFICATION_STATUSES:
        message = "Verification status must be one of: " + ", ".join(VERIFICATION_STATUSES)
        result.checks.append(_coerce_check("worker_result_verification_status_valid", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _coerce_check(
            "worker_result_verification_status_valid",
            "pass",
            f"Verification status is valid: {raw_verification_status}",
        )
    )

    string_list_field_names = (
        "actions_performed",
        "files_read",
        "files_changed",
        "commands_run",
        "unresolved_issues",
        "escalation_notes",
    )
    normalized_string_lists: dict[str, list[str]] = {}
    list_errors: list[str] = []
    for field_name in string_list_field_names:
        normalized_values = _normalize_string_list(payload.get(field_name), allow_empty=True)
        if isinstance(normalized_values, str):
            list_errors.append(f"Field '{field_name}' {normalized_values}")
            continue
        normalized_string_lists[field_name] = normalized_values

    if list_errors:
        message = "Invalid worker result list fields: " + "; ".join(list_errors)
        result.checks.append(_coerce_check("worker_result_list_fields_valid", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _coerce_check(
            "worker_result_list_fields_valid",
            "pass",
            "Required worker result list fields are valid.",
        )
    )

    command_results = _normalize_command_results(payload.get("command_results"))
    if isinstance(command_results, str):
        result.checks.append(_coerce_check("worker_result_command_results_valid", "fail", command_results))
        result.errors.append(command_results)
        return result

    result.checks.append(
        _coerce_check(
            "worker_result_command_results_valid",
            "pass",
            "Command result entries are valid.",
        )
    )

    required_outputs_status = _normalize_item_status_list(
        payload.get("required_outputs_status"),
        field_name="required_outputs_status",
        allow_empty=False,
    )
    if isinstance(required_outputs_status, str):
        result.checks.append(_coerce_check("worker_result_required_outputs_status_valid", "fail", required_outputs_status))
        result.errors.append(required_outputs_status)
        return result

    result.checks.append(
        _coerce_check(
            "worker_result_required_outputs_status_valid",
            "pass",
            "Required output status entries are valid.",
        )
    )

    success_criteria_status = _normalize_item_status_list(
        payload.get("success_criteria_status"),
        field_name="success_criteria_status",
        allow_empty=False,
    )
    if isinstance(success_criteria_status, str):
        result.checks.append(_coerce_check("worker_result_success_criteria_status_valid", "fail", success_criteria_status))
        result.errors.append(success_criteria_status)
        return result

    result.checks.append(
        _coerce_check(
            "worker_result_success_criteria_status_valid",
            "pass",
            "Success criteria status entries are valid.",
        )
    )

    result.parsed_result = NormalizedWorkerResult(
        task_id=normalized_task_id,
        worker_role=normalized_worker_role,
        status=raw_status,
        summary=normalized_summary,
        actions_performed=normalized_string_lists["actions_performed"],
        files_read=normalized_string_lists["files_read"],
        files_changed=normalized_string_lists["files_changed"],
        commands_run=normalized_string_lists["commands_run"],
        command_results=command_results,
        verification_status=raw_verification_status,
        required_outputs_status=required_outputs_status,
        success_criteria_status=success_criteria_status,
        unresolved_issues=normalized_string_lists["unresolved_issues"],
        escalation_notes=normalized_string_lists["escalation_notes"],
    )
    result.status = "success"
    return result


def adjudicate_worker_result_payload(
    payload: Any,
    input_path: Path | None = None,
) -> AdjudicationResult:
    validation = validate_worker_result_payload(payload=payload, input_path=input_path)

    if validation.status != "success" or validation.parsed_result is None:
        reason = validation.errors[0] if validation.errors else "Worker result payload is invalid."
        checks = list(validation.checks)
        checks.append(
            _coerce_check(
                "adjudication_decision",
                "fail",
                "Adjudication rejected the worker result because the payload is invalid.",
            )
        )
        return AdjudicationResult(
            task_id=validation.task_id,
            decision="reject",
            reason=reason,
            status="rejected",
            required_outputs_satisfied=False,
            success_criteria_satisfied=False,
            unresolved_issues_present=False,
            escalation_requested=False,
            next_action="Fix the worker result payload and rerun adjudication.",
            input_path=input_path,
            worker_result_status=None,
            checks=checks,
            errors=list(validation.errors),
        )

    normalized = validation.parsed_result
    required_outputs_satisfied = all(
        item.status == "satisfied" for item in normalized.required_outputs_status
    )
    success_criteria_satisfied = all(
        item.status == "satisfied" for item in normalized.success_criteria_status
    )
    unresolved_issues_present = bool(normalized.unresolved_issues)
    escalation_requested = normalized.status == "blocked" or bool(normalized.escalation_notes)

    checks = list(validation.checks)
    checks.extend(
        [
            _coerce_check(
                "required_outputs_satisfied",
                "pass" if required_outputs_satisfied else "fail",
                "All required outputs are satisfied."
                if required_outputs_satisfied
                else "One or more required outputs are not satisfied.",
            ),
            _coerce_check(
                "success_criteria_satisfied",
                "pass" if success_criteria_satisfied else "fail",
                "All success criteria are satisfied."
                if success_criteria_satisfied
                else "One or more success criteria are not satisfied.",
            ),
            _coerce_check(
                "unresolved_issues_absent",
                "pass" if not unresolved_issues_present else "fail",
                "No unresolved issues remain."
                if not unresolved_issues_present
                else "Unresolved issues remain in the worker result.",
            ),
            _coerce_check(
                "escalation_requested_absent",
                "pass" if not escalation_requested else "fail",
                "No escalation was requested."
                if not escalation_requested
                else "The worker result requests escalation or is blocked.",
            ),
        ]
    )

    if escalation_requested:
        checks.append(
            _coerce_check(
                "adjudication_decision",
                "pass",
                "Adjudication decided to escalate the worker result.",
            )
        )
        return AdjudicationResult(
            task_id=normalized.task_id,
            decision="escalate",
            reason=(
                "Worker result is blocked or explicitly requested escalation."
            ),
            status="adjudicated",
            required_outputs_satisfied=required_outputs_satisfied,
            success_criteria_satisfied=success_criteria_satisfied,
            unresolved_issues_present=unresolved_issues_present,
            escalation_requested=True,
            next_action="Route the task to the orchestrator for a higher-level decision.",
            input_path=input_path,
            worker_result_status=normalized.status,
            checks=checks,
            errors=[],
        )

    if (
        normalized.status == "success"
        and required_outputs_satisfied
        and success_criteria_satisfied
        and not unresolved_issues_present
    ):
        checks.append(
            _coerce_check(
                "adjudication_decision",
                "pass",
                "Adjudication accepted the worker result.",
            )
        )
        return AdjudicationResult(
            task_id=normalized.task_id,
            decision="accept",
            reason="Worker result satisfies the bounded task and needs no escalation.",
            status="adjudicated",
            required_outputs_satisfied=True,
            success_criteria_satisfied=True,
            unresolved_issues_present=False,
            escalation_requested=False,
            next_action="Accept the bounded result and update the implementation record.",
            input_path=input_path,
            worker_result_status=normalized.status,
            checks=checks,
            errors=[],
        )

    checks.append(
        _coerce_check(
            "adjudication_decision",
            "pass",
            "Adjudication decided the task should be retried.",
        )
    )
    return AdjudicationResult(
        task_id=normalized.task_id,
        decision="retry",
        reason="Worker result is valid but the bounded task is not yet complete.",
        status="adjudicated",
        required_outputs_satisfied=required_outputs_satisfied,
        success_criteria_satisfied=success_criteria_satisfied,
        unresolved_issues_present=unresolved_issues_present,
        escalation_requested=False,
        next_action="Revise or repeat the bounded task and return a new worker result.",
        input_path=input_path,
        worker_result_status=normalized.status,
        checks=checks,
        errors=[],
    )


def adjudicate_worker_result_file(input_path: Path) -> AdjudicationResult:
    resolved_input_path = input_path.expanduser().resolve()
    if not resolved_input_path.is_file():
        message = f"Missing worker result input file: {resolved_input_path}"
        return AdjudicationResult(
            task_id=None,
            decision="reject",
            reason=message,
            status="rejected",
            required_outputs_satisfied=False,
            success_criteria_satisfied=False,
            unresolved_issues_present=False,
            escalation_requested=False,
            next_action="Create the worker result JSON file and rerun adjudication.",
            input_path=resolved_input_path,
            worker_result_status=None,
            checks=[_coerce_check("worker_result_input_exists", "fail", message)],
            errors=[message],
        )

    try:
        with resolved_input_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        message = f"Failed to parse worker result JSON in {resolved_input_path}: {exc}"
        return AdjudicationResult(
            task_id=None,
            decision="reject",
            reason=message,
            status="rejected",
            required_outputs_satisfied=False,
            success_criteria_satisfied=False,
            unresolved_issues_present=False,
            escalation_requested=False,
            next_action="Fix the worker result JSON file and rerun adjudication.",
            input_path=resolved_input_path,
            worker_result_status=None,
            checks=[
                _coerce_check(
                    "worker_result_input_exists",
                    "pass",
                    f"Found worker result input file: {resolved_input_path}",
                ),
                _coerce_check("worker_result_json_parses", "fail", message),
            ],
            errors=[message],
        )
    except OSError as exc:
        message = f"Failed to read worker result file {resolved_input_path}: {exc}"
        return AdjudicationResult(
            task_id=None,
            decision="reject",
            reason=message,
            status="rejected",
            required_outputs_satisfied=False,
            success_criteria_satisfied=False,
            unresolved_issues_present=False,
            escalation_requested=False,
            next_action="Fix the worker result file and rerun adjudication.",
            input_path=resolved_input_path,
            worker_result_status=None,
            checks=[_coerce_check("worker_result_input_exists", "fail", message)],
            errors=[message],
        )

    result = adjudicate_worker_result_payload(payload=payload, input_path=resolved_input_path)
    checks = [
        _coerce_check(
            "worker_result_input_exists",
            "pass",
            f"Found worker result input file: {resolved_input_path}",
        ),
        _coerce_check(
            "worker_result_json_parses",
            "pass",
            "Parsed worker result JSON successfully.",
        ),
    ]
    result.checks = checks + result.checks
    return result


def format_worker_handoff_summary(result: WorkerHandoffBuildResult) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")

    lines = [
        f"build-worker-handoff: {result.status.upper()}",
        f"project root: {result.project_root}",
        f"task path: {result.task_path}",
        f"task id: {result.task_id if result.task_id is not None else 'none'}",
        f"worker role: {result.worker_role if result.worker_role else 'none'}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
    ]

    if failed:
        lines.append("failures:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")
    else:
        lines.append("summary: worker handoff payload is ready for bounded delegation.")

    return "\n".join(lines)


def format_adjudication_summary(result: AdjudicationResult) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")

    lines = [
        f"adjudicate-worker-result: {result.decision.upper()}",
        f"task id: {result.task_id if result.task_id is not None else 'none'}",
        f"status: {result.status}",
        f"worker result status: {result.worker_result_status if result.worker_result_status is not None else 'none'}",
        f"required outputs satisfied: {'yes' if result.required_outputs_satisfied else 'no'}",
        f"success criteria satisfied: {'yes' if result.success_criteria_satisfied else 'no'}",
        f"unresolved issues present: {'yes' if result.unresolved_issues_present else 'no'}",
        f"escalation requested: {'yes' if result.escalation_requested else 'no'}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
        f"reason: {result.reason}",
        f"next action: {result.next_action}",
    ]

    if failed:
        lines.append("failures:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")

    return "\n".join(lines)


def _build_payload_from_task(
    project_root: Path,
    task: NormalizedTaskSpec,
    worker_role: str,
    policy_reference: str | None,
) -> WorkerHandoffPayload:
    return WorkerHandoffPayload(
        task_id=task.task_id,
        title=task.title,
        goal=task.goal,
        scope=list(task.scope),
        non_goals=list(task.non_goals),
        required_outputs=list(task.required_outputs),
        success_criteria=list(task.success_criteria),
        project_root=str(project_root),
        worker_role=worker_role,
        expected_result_fields=list(EXPECTED_RESULT_FIELDS),
        notes=task.notes,
        allowed_roots=list(task.allowed_roots) if task.allowed_roots is not None else None,
        suggested_commands=list(task.suggested_commands) if task.suggested_commands is not None else None,
        verification_commands=list(task.verification_commands) if task.verification_commands is not None else None,
        implementation_record_path=task.implementation_record_path,
        policy_reference=policy_reference,
    )


def _normalize_command_results(value: Any) -> list[CommandResultEntry] | str:
    if not isinstance(value, list):
        return "Field 'command_results' must be a list of command result objects."

    normalized_entries: list[CommandResultEntry] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return f"Field 'command_results' contains a non-object entry at index {index}."

        command = _normalize_non_empty_string(item.get("command"))
        outcome = _normalize_non_empty_string(item.get("outcome"))
        if command is None:
            return f"Field 'command_results' entry {index} requires a non-empty string field 'command'."
        if outcome is None:
            return f"Field 'command_results' entry {index} requires a non-empty string field 'outcome'."
        if outcome not in COMMAND_OUTCOMES:
            return (
                f"Field 'command_results' entry {index} has invalid outcome '{outcome}'. "
                f"Expected one of: {', '.join(COMMAND_OUTCOMES)}"
            )

        exit_code = item.get("exit_code")
        if exit_code is not None and not isinstance(exit_code, int):
            return f"Field 'command_results' entry {index} has a non-integer 'exit_code'."

        summary = item.get("summary")
        if summary is not None:
            summary = _normalize_non_empty_string(summary)
            if summary is None:
                return f"Field 'command_results' entry {index} has an invalid 'summary'."

        evidence_ref = item.get("evidence_ref")
        if evidence_ref is not None:
            evidence_ref = _normalize_non_empty_string(evidence_ref)
            if evidence_ref is None:
                return f"Field 'command_results' entry {index} has an invalid 'evidence_ref'."

        normalized_entries.append(
            CommandResultEntry(
                command=command,
                outcome=outcome,
                exit_code=exit_code,
                summary=summary,
                evidence_ref=evidence_ref,
            )
        )

    return normalized_entries


def _normalize_item_status_list(
    value: Any,
    field_name: str,
    allow_empty: bool,
) -> list[ItemStatusEntry] | str:
    if not isinstance(value, list):
        return f"Field '{field_name}' must be a list of status objects."
    if not allow_empty and not value:
        return f"Field '{field_name}' must be a non-empty list of status objects."

    normalized_entries: list[ItemStatusEntry] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return f"Field '{field_name}' contains a non-object entry at index {index}."

        name = _normalize_non_empty_string(item.get("name"))
        status = _normalize_non_empty_string(item.get("status"))
        if name is None:
            return f"Field '{field_name}' entry {index} requires a non-empty string field 'name'."
        if status is None:
            return f"Field '{field_name}' entry {index} requires a non-empty string field 'status'."
        if status not in ITEM_STATUS_VALUES:
            return (
                f"Field '{field_name}' entry {index} has invalid status '{status}'. "
                f"Expected one of: {', '.join(ITEM_STATUS_VALUES)}"
            )

        details = item.get("details")
        if details is not None:
            details = _normalize_non_empty_string(details)
            if details is None:
                return f"Field '{field_name}' entry {index} has an invalid 'details'."

        normalized_entries.append(ItemStatusEntry(name=name, status=status, details=details))

    return normalized_entries


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


def _coerce_check(name: str, status: str, message: str) -> ControlLoopCheck:
    return ControlLoopCheck(name=name, status=status, message=message)