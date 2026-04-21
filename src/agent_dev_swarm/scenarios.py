from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from agent_dev_swarm.handoff_adjudication import validate_worker_result_payload
from agent_dev_swarm.sandbox_fixtures import DEFAULT_FIXTURES_ROOT, DEFAULT_RUNS_ROOT, REPO_ROOT, materialize_sandbox_run
from agent_dev_swarm.supervised_runs import scaffold_supervised_run

SCENARIO_VERSION = "1"
DEFAULT_SCENARIOS_ROOT = REPO_ROOT / "scenarios"

REQUIRED_STRING_FIELDS = (
    "scenario_id",
    "description",
    "scenario_version",
    "fixture",
    "worker_role",
    "provider",
    "model",
    "expected_outcome",
)
REQUIRED_BOOLEAN_FIELDS = ("allow_remote_models", "reset_before_run")
OPTIONAL_STRING_FIELDS = ("task", "policy", "run_id_prefix", "notes")
OPTIONAL_LIST_FIELDS = ("context_files",)
OPTIONAL_INTEGER_FIELDS = ("timeout_seconds",)
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(slots=True)
class ScenarioCheck:
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
class ScenarioDefinition:
    scenario_id: str
    description: str
    scenario_version: str
    fixture: str
    worker_role: str
    provider: str
    model: str
    allow_remote_models: bool
    reset_before_run: bool
    expected_outcome: str
    task: str | None = None
    policy: str | None = None
    run_id_prefix: str | None = None
    notes: str | None = None
    context_files: list[str] = field(default_factory=list)
    timeout_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "scenario_version": self.scenario_version,
            "fixture": self.fixture,
            "worker_role": self.worker_role,
            "provider": self.provider,
            "model": self.model,
            "allow_remote_models": self.allow_remote_models,
            "reset_before_run": self.reset_before_run,
            "expected_outcome": self.expected_outcome,
            "context_files": list(self.context_files),
        }
        if self.task is not None:
            payload["task"] = self.task
        if self.policy is not None:
            payload["policy"] = self.policy
        if self.run_id_prefix is not None:
            payload["run_id_prefix"] = self.run_id_prefix
        if self.notes is not None:
            payload["notes"] = self.notes
        if self.timeout_seconds is not None:
            payload["timeout_seconds"] = self.timeout_seconds
        return payload


@dataclass(slots=True)
class ScenarioLoadResult:
    status: str
    scenario_ref: str
    scenario_path: Path
    scenario_id: str | None = None
    checks: list[ScenarioCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    scenario: ScenarioDefinition | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scenario_ref": self.scenario_ref,
            "scenario_path": str(self.scenario_path),
            "scenario_id": self.scenario_id,
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "scenario": self.scenario.to_dict() if self.scenario is not None else None,
        }


@dataclass(slots=True)
class LocalWorkerInvocationResult:
    status: str
    provider: str
    model: str
    command: list[str]
    raw_output: str
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "command": list(self.command),
            "raw_output": self.raw_output,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "error": self.error,
        }


@dataclass(slots=True)
class ScenarioRunResult:
    status: str
    scenario_id: str
    scenario_path: Path
    run_id: str
    run_root: Path
    workspace_root: Path
    artifacts_root: Path
    fixture: str
    worker_role: str
    provider: str
    model: str
    handoff_path: Path | None = None
    worker_result_starter_path: Path | None = None
    worker_result_path: Path | None = None
    raw_output_path: Path | None = None
    prompt_path: Path | None = None
    invocation_path: Path | None = None
    scenario_summary_path: Path | None = None
    checks: list[ScenarioCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_paths: list[str] = field(default_factory=list)
    reset_performed: bool = False
    candidate_result_written: bool = False
    candidate_result_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scenario_id": self.scenario_id,
            "scenario_path": str(self.scenario_path),
            "run_id": self.run_id,
            "run_root": str(self.run_root),
            "workspace_root": str(self.workspace_root),
            "artifacts_root": str(self.artifacts_root),
            "fixture": self.fixture,
            "worker_role": self.worker_role,
            "provider": self.provider,
            "model": self.model,
            "handoff_path": str(self.handoff_path) if self.handoff_path is not None else None,
            "worker_result_starter_path": (
                str(self.worker_result_starter_path)
                if self.worker_result_starter_path is not None
                else None
            ),
            "worker_result_path": str(self.worker_result_path) if self.worker_result_path is not None else None,
            "raw_output_path": str(self.raw_output_path) if self.raw_output_path is not None else None,
            "prompt_path": str(self.prompt_path) if self.prompt_path is not None else None,
            "invocation_path": str(self.invocation_path) if self.invocation_path is not None else None,
            "scenario_summary_path": (
                str(self.scenario_summary_path) if self.scenario_summary_path is not None else None
            ),
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "created_paths": list(self.created_paths),
            "reset_performed": self.reset_performed,
            "candidate_result_written": self.candidate_result_written,
            "candidate_result_message": self.candidate_result_message,
        }


WorkerInvoker = Callable[[str, str, int | None], LocalWorkerInvocationResult]


def load_scenario(
    scenario: str,
    scenarios_root: Path | None = None,
) -> ScenarioLoadResult:
    resolved_scenarios_root = (scenarios_root or DEFAULT_SCENARIOS_ROOT).expanduser().resolve()
    scenario_ref = scenario.strip()
    scenario_path = _resolve_scenario_path(resolved_scenarios_root, scenario_ref)
    result = ScenarioLoadResult(
        status="failure",
        scenario_ref=scenario_ref,
        scenario_path=scenario_path,
    )

    if not scenario_path.is_file():
        message = f"Missing scenario file: {scenario_path}"
        result.checks.append(_check("scenario_file_exists", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("scenario_file_exists", "pass", f"Found scenario file: {scenario_path}")
    )

    raw_scenario = _parse_scenario_yaml(scenario_path)
    if isinstance(raw_scenario, str):
        result.checks.append(_check("scenario_yaml_parses", "fail", raw_scenario))
        result.errors.append(raw_scenario)
        return result

    result.checks.append(
        _check("scenario_yaml_parses", "pass", "Parsed scenario YAML successfully.")
    )

    if not isinstance(raw_scenario, dict):
        message = f"Expected YAML mapping in {scenario_path}, got {type(raw_scenario).__name__}."
        result.checks.append(_check("scenario_top_level_mapping", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("scenario_top_level_mapping", "pass", "Scenario top-level YAML structure is a mapping.")
    )

    parsed = _build_scenario_definition(scenario_ref, raw_scenario)
    if isinstance(parsed, str):
        result.checks.append(_check("scenario_fields_valid", "fail", parsed))
        result.errors.append(parsed)
        return result

    result.scenario_id = parsed.scenario_id
    result.scenario = parsed
    result.checks.append(_check("scenario_fields_valid", "pass", "Scenario fields are valid."))

    if parsed.provider != "ollama":
        message = (
            f"Unsupported scenario provider '{parsed.provider}'. This runner currently supports only local-only provider 'ollama'."
        )
        result.checks.append(_check("provider_supported", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(_check("provider_supported", "pass", "Scenario provider is supported: ollama"))

    if parsed.allow_remote_models:
        message = "Scenario must set allow_remote_models: false for local-only execution."
        result.checks.append(_check("local_only_configured", "fail", message))
        result.errors.append(message)
        return result

    result.checks.append(
        _check("local_only_configured", "pass", "Scenario is configured for explicit local-only execution.")
    )

    result.status = "success"
    return result


def run_scenario(
    scenario: str,
    scenarios_root: Path | None = None,
    fixtures_root: Path | None = None,
    runs_root: Path | None = None,
    invoker: WorkerInvoker | None = None,
) -> ScenarioRunResult:
    load_result = load_scenario(scenario, scenarios_root=scenarios_root)
    scenario_path = load_result.scenario_path
    scenario_id = load_result.scenario_id or scenario.strip()

    if load_result.status != "success" or load_result.scenario is None:
        return ScenarioRunResult(
            status="failure",
            scenario_id=scenario_id,
            scenario_path=scenario_path,
            run_id=scenario_id,
            run_root=(runs_root or DEFAULT_RUNS_ROOT).expanduser().resolve() / scenario_id,
            workspace_root=((runs_root or DEFAULT_RUNS_ROOT).expanduser().resolve() / scenario_id / "workspace"),
            artifacts_root=((runs_root or DEFAULT_RUNS_ROOT).expanduser().resolve() / scenario_id / "artifacts"),
            fixture="none",
            worker_role="none",
            provider="none",
            model="none",
            checks=list(load_result.checks),
            errors=list(load_result.errors),
        )

    scenario_definition = load_result.scenario
    resolved_runs_root = (runs_root or DEFAULT_RUNS_ROOT).expanduser().resolve()
    run_id = scenario_definition.run_id_prefix or scenario_definition.scenario_id
    run_root = resolved_runs_root / run_id
    workspace_root = run_root / "workspace"
    artifacts_root = run_root / "artifacts"

    result = ScenarioRunResult(
        status="failure",
        scenario_id=scenario_definition.scenario_id,
        scenario_path=scenario_path,
        run_id=run_id,
        run_root=run_root,
        workspace_root=workspace_root,
        artifacts_root=artifacts_root,
        fixture=scenario_definition.fixture,
        worker_role=scenario_definition.worker_role,
        provider=scenario_definition.provider,
        model=scenario_definition.model,
        checks=list(load_result.checks),
        errors=list(load_result.errors),
    )

    materialize_result = materialize_sandbox_run(
        fixture_name=scenario_definition.fixture,
        run_id=run_id,
        force_reset=scenario_definition.reset_before_run,
        fixtures_root=fixtures_root,
        runs_root=runs_root,
    )
    result.checks.extend(_prefix_checks("sandbox", materialize_result.checks))
    result.created_paths.extend(materialize_result.created_paths)
    result.reset_performed = materialize_result.reset_performed
    if materialize_result.status != "success":
        result.errors.extend(materialize_result.errors)
        return result

    scaffold_result = scaffold_supervised_run(
        run_id=run_id,
        worker_role=scenario_definition.worker_role,
        task=scenario_definition.task,
        policy=scenario_definition.policy,
        force_overwrite=scenario_definition.reset_before_run,
        runs_root=runs_root,
    )
    result.checks.extend(_prefix_checks("supervised", scaffold_result.checks))
    result.created_paths.extend(scaffold_result.created_paths)
    result.workspace_root = scaffold_result.workspace_root
    result.artifacts_root = scaffold_result.artifacts_root
    result.handoff_path = scaffold_result.handoff_path
    result.worker_result_starter_path = scaffold_result.worker_result_starter_path
    if scaffold_result.status != "success":
        result.errors.extend(scaffold_result.errors)
        return result

    if result.handoff_path is None or not result.handoff_path.is_file():
        message = f"Missing worker handoff artifact after supervised scaffold: {result.handoff_path}"
        result.checks.append(_check("worker_handoff_exists", "fail", message))
        result.errors.append(message)
        return result
    result.checks.append(_check("worker_handoff_exists", "pass", f"Found worker handoff artifact: {result.handoff_path}"))

    if result.worker_result_starter_path is None or not result.worker_result_starter_path.is_file():
        message = f"Missing worker-result starter artifact after supervised scaffold: {result.worker_result_starter_path}"
        result.checks.append(_check("worker_result_starter_exists", "fail", message))
        result.errors.append(message)
        return result
    result.checks.append(
        _check(
            "worker_result_starter_exists",
            "pass",
            f"Found worker-result starter artifact: {result.worker_result_starter_path}",
        )
    )

    context_result = _resolve_context_files(result.workspace_root, scenario_definition.context_files)
    result.checks.extend(context_result[1])
    if isinstance(context_result[0], str):
        result.errors.append(context_result[0])
        return result
    context_files = context_result[0]

    handoff_payload = _load_json_file(result.handoff_path)
    if isinstance(handoff_payload, str) or not isinstance(handoff_payload, dict):
        message = handoff_payload if isinstance(handoff_payload, str) else f"Invalid handoff JSON payload in {result.handoff_path}"
        result.checks.append(_check("worker_handoff_parses", "fail", message))
        result.errors.append(message)
        return result
    result.checks.append(_check("worker_handoff_parses", "pass", "Parsed worker handoff JSON successfully."))

    starter_payload = _load_json_file(result.worker_result_starter_path)
    if isinstance(starter_payload, str) or not isinstance(starter_payload, dict):
        message = starter_payload if isinstance(starter_payload, str) else f"Invalid worker-result starter JSON in {result.worker_result_starter_path}"
        result.checks.append(_check("worker_result_starter_parses", "fail", message))
        result.errors.append(message)
        return result
    result.checks.append(_check("worker_result_starter_parses", "pass", "Parsed worker-result starter JSON successfully."))

    prompt = _build_scenario_prompt(
        scenario=scenario_definition,
        handoff_payload=handoff_payload,
        starter_payload=starter_payload,
        context_files=context_files,
    )
    prompt_path = result.artifacts_root / "commands" / "worker-prompt.txt"
    _write_text(prompt_path, prompt)
    result.prompt_path = prompt_path
    result.created_paths.append(str(prompt_path))
    result.checks.append(_check("worker_prompt_written", "pass", f"Wrote worker prompt artifact: {prompt_path}"))

    invocation_result = (invoker or invoke_ollama_worker)(
        scenario_definition.model,
        prompt,
        scenario_definition.timeout_seconds,
    )
    invocation_path = result.artifacts_root / "commands" / "worker-invocation.json"
    raw_output_path = result.artifacts_root / "worker-result" / "raw-model-output.txt"
    _write_json(invocation_path, invocation_result.to_dict())
    _write_text(raw_output_path, invocation_result.raw_output)
    result.invocation_path = invocation_path
    result.raw_output_path = raw_output_path
    result.created_paths.extend([str(invocation_path), str(raw_output_path)])

    if invocation_result.status != "success":
        message = invocation_result.error or "Local worker invocation failed."
        result.checks.append(_check("local_worker_invoked", "fail", message))
        result.errors.append(message)
        return result
    result.checks.append(
        _check(
            "local_worker_invoked",
            "pass",
            f"Invoked local worker provider {invocation_result.provider} with model {invocation_result.model}.",
        )
    )

    candidate_result = _extract_worker_result_candidate(invocation_result.raw_output)
    candidate_path = result.artifacts_root / "worker-result" / "worker-result.json"
    if isinstance(candidate_result, dict):
        normalized_candidate = _normalize_worker_result_candidate(candidate_result)
        validation = validate_worker_result_payload(normalized_candidate)
        if validation.status == "success":
            _write_json(candidate_path, normalized_candidate)
            result.worker_result_path = candidate_path
            result.candidate_result_written = True
            result.candidate_result_message = "Wrote validated worker result candidate from local model output."
            result.created_paths.append(str(candidate_path))
            result.checks.append(_check("worker_result_candidate_written", "pass", result.candidate_result_message))
        else:
            result.candidate_result_message = (
                validation.errors[0] if validation.errors else "Local model output did not validate as a worker result payload."
            )
            result.checks.append(
                _check(
                    "worker_result_candidate_written",
                    "pass",
                    "Raw output was captured, but the worker result candidate was not written because it did not validate.",
                )
            )
    else:
        result.candidate_result_message = candidate_result
        result.checks.append(
            _check(
                "worker_result_candidate_written",
                "pass",
                "Raw output was captured, but no JSON worker result candidate could be extracted automatically.",
            )
        )

    result.status = "success"
    scenario_summary_path = result.artifacts_root / "summary" / "scenario-run-summary.json"
    result.scenario_summary_path = scenario_summary_path
    _write_json(
        scenario_summary_path,
        {
            "scenario": scenario_definition.to_dict(),
            "run_result": result.to_dict(),
            "invocation": invocation_result.to_dict(),
        },
    )
    result.created_paths.append(str(scenario_summary_path))
    result.checks.append(
        _check("scenario_summary_written", "pass", f"Wrote scenario summary artifact: {scenario_summary_path}")
    )
    return result


def invoke_ollama_worker(model: str, prompt: str, timeout_seconds: int | None) -> LocalWorkerInvocationResult:
    command = ["ollama", "run", "--hidethinking", "--nowordwrap", model, prompt]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return LocalWorkerInvocationResult(
            status="failure",
            provider="ollama",
            model=model,
            command=command,
            raw_output=_coerce_stream_data(exc.stdout),
            stderr=_coerce_stream_data(exc.stderr),
            exit_code=None,
            timed_out=True,
            error=f"Local Ollama invocation exceeded timeout of {timeout_seconds} seconds.",
        )
    except OSError as exc:
        return LocalWorkerInvocationResult(
            status="failure",
            provider="ollama",
            model=model,
            command=command,
            raw_output="",
            stderr="",
            exit_code=None,
            timed_out=False,
            error=f"Failed to start local Ollama invocation: {exc}",
        )

    if completed.returncode != 0:
        return LocalWorkerInvocationResult(
            status="failure",
            provider="ollama",
            model=model,
            command=command,
            raw_output=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            timed_out=False,
            error=f"Local Ollama invocation exited with status {completed.returncode}.",
        )

    return LocalWorkerInvocationResult(
        status="success",
        provider="ollama",
        model=model,
        command=command,
        raw_output=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        timed_out=False,
        error=None,
    )


def format_scenario_run_summary(result: ScenarioRunResult) -> str:
    passed = sum(1 for check in result.checks if check.status == "pass")
    failed = sum(1 for check in result.checks if check.status == "fail")
    lines = [
        f"run-scenario: {result.status.upper()}",
        f"scenario id: {result.scenario_id}",
        f"run id: {result.run_id}",
        f"fixture: {result.fixture}",
        f"provider: {result.provider}",
        f"model: {result.model}",
        f"run root: {result.run_root}",
        f"handoff path: {result.handoff_path if result.handoff_path is not None else 'none'}",
        f"worker-result starter path: {result.worker_result_starter_path if result.worker_result_starter_path is not None else 'none'}",
        f"worker-result path: {result.worker_result_path if result.worker_result_path is not None else 'none'}",
        f"raw output path: {result.raw_output_path if result.raw_output_path is not None else 'none'}",
        f"scenario summary path: {result.scenario_summary_path if result.scenario_summary_path is not None else 'none'}",
        f"checks passed: {passed}",
        f"checks failed: {failed}",
    ]

    if failed:
        lines.append("failures:")
        for check in result.checks:
            if check.status == "fail":
                lines.append(f"- {check.message}")
    else:
        lines.append("summary: scenario run completed and left stable artifacts for review.")

    if result.candidate_result_message is not None:
        lines.append(f"worker result note: {result.candidate_result_message}")

    return "\n".join(lines)


def _resolve_scenario_path(scenarios_root: Path, scenario: str) -> Path:
    candidate = Path(scenario)
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.suffix in {".yaml", ".yml"} or len(candidate.parts) > 1:
        return (scenarios_root / candidate).resolve()
    return (scenarios_root / f"{scenario}.yaml").resolve()


def _parse_scenario_yaml(path: Path) -> Any | str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return f"Failed to parse scenario YAML in {path}: {exc}"
    except OSError as exc:
        return f"Failed to read scenario file {path}: {exc}"


def _build_scenario_definition(scenario_ref: str, raw: dict[str, Any]) -> ScenarioDefinition | str:
    missing_fields = [
        field_name
        for field_name in (*REQUIRED_STRING_FIELDS, *REQUIRED_BOOLEAN_FIELDS)
        if field_name not in raw
    ]
    if missing_fields:
        return "Missing required scenario fields: " + ", ".join(missing_fields)

    normalized_strings: dict[str, str] = {}
    string_errors: list[str] = []
    for field_name in REQUIRED_STRING_FIELDS:
        normalized_value = _normalize_non_empty_string(raw.get(field_name))
        if normalized_value is None:
            string_errors.append(f"Field '{field_name}' must be a non-empty string.")
            continue
        normalized_strings[field_name] = normalized_value

    optional_strings: dict[str, str] = {}
    for field_name in OPTIONAL_STRING_FIELDS:
        if field_name not in raw:
            continue
        normalized_value = _normalize_non_empty_string(raw.get(field_name))
        if normalized_value is None:
            string_errors.append(f"Field '{field_name}' must be a non-empty string when provided.")
            continue
        optional_strings[field_name] = normalized_value

    if string_errors:
        return "Invalid scenario string fields: " + "; ".join(string_errors)

    if normalized_strings["scenario_version"] != SCENARIO_VERSION:
        return (
            f"Unsupported scenario_version '{normalized_strings['scenario_version']}'. Expected {SCENARIO_VERSION}."
        )

    if scenario_ref and Path(scenario_ref).suffix not in {".yaml", ".yml"} and len(Path(scenario_ref).parts) == 1:
        if normalized_strings["scenario_id"] != scenario_ref:
            return (
                f"Scenario id '{normalized_strings['scenario_id']}' does not match requested scenario ref '{scenario_ref}'."
            )

    boolean_values: dict[str, bool] = {}
    boolean_errors: list[str] = []
    for field_name in REQUIRED_BOOLEAN_FIELDS:
        value = raw.get(field_name)
        if not isinstance(value, bool):
            boolean_errors.append(f"Field '{field_name}' must be a boolean.")
            continue
        boolean_values[field_name] = value

    if boolean_errors:
        return "Invalid scenario boolean fields: " + "; ".join(boolean_errors)

    optional_lists: dict[str, list[str]] = {}
    list_errors: list[str] = []
    for field_name in OPTIONAL_LIST_FIELDS:
        if field_name not in raw:
            continue
        normalized_list = _normalize_relative_string_list(raw.get(field_name))
        if isinstance(normalized_list, str):
            list_errors.append(f"Field '{field_name}' {normalized_list}")
            continue
        optional_lists[field_name] = normalized_list

    if list_errors:
        return "Invalid scenario list fields: " + "; ".join(list_errors)

    optional_integers: dict[str, int] = {}
    integer_errors: list[str] = []
    for field_name in OPTIONAL_INTEGER_FIELDS:
        if field_name not in raw:
            continue
        value = raw.get(field_name)
        if not isinstance(value, int) or value <= 0:
            integer_errors.append(f"Field '{field_name}' must be a positive integer when provided.")
            continue
        optional_integers[field_name] = value

    if integer_errors:
        return "Invalid scenario integer fields: " + "; ".join(integer_errors)

    return ScenarioDefinition(
        scenario_id=normalized_strings["scenario_id"],
        description=normalized_strings["description"],
        scenario_version=normalized_strings["scenario_version"],
        fixture=normalized_strings["fixture"],
        worker_role=normalized_strings["worker_role"],
        provider=normalized_strings["provider"].lower(),
        model=normalized_strings["model"],
        allow_remote_models=boolean_values["allow_remote_models"],
        reset_before_run=boolean_values["reset_before_run"],
        expected_outcome=normalized_strings["expected_outcome"],
        task=optional_strings.get("task"),
        policy=optional_strings.get("policy"),
        run_id_prefix=optional_strings.get("run_id_prefix"),
        notes=optional_strings.get("notes"),
        context_files=optional_lists.get("context_files", []),
        timeout_seconds=optional_integers.get("timeout_seconds"),
    )


def _resolve_context_files(
    workspace_root: Path,
    context_files: list[str],
) -> tuple[dict[str, str] | str, list[ScenarioCheck]]:
    checks: list[ScenarioCheck] = []
    resolved: dict[str, str] = {}
    for relative_path in context_files:
        resolved_path = (workspace_root / relative_path).resolve()
        if not _is_relative_to(resolved_path, workspace_root):
            message = f"Context file escapes the sandbox workspace: {relative_path}"
            checks.append(_check("context_files_resolved", "fail", message))
            return message, checks
        if not resolved_path.is_file():
            message = f"Missing context file in the sandbox workspace: {resolved_path}"
            checks.append(_check("context_files_resolved", "fail", message))
            return message, checks
        resolved[relative_path] = resolved_path.read_text(encoding="utf-8")

    checks.append(
        _check(
            "context_files_resolved",
            "pass",
            "Resolved scenario context files successfully."
            if context_files
            else "Scenario does not require extra context files.",
        )
    )
    return resolved, checks


def _build_scenario_prompt(
    scenario: ScenarioDefinition,
    handoff_payload: dict[str, Any],
    starter_payload: dict[str, Any],
    context_files: dict[str, str],
) -> str:
    context_sections = []
    for relative_path, content in context_files.items():
        context_sections.append(
            "\n".join(
                [
                    f"FILE: {relative_path}",
                    "```text",
                    content.rstrip(),
                    "```",
                ]
            )
        )

    sections = [
        "You are a local-only implementation worker running inside agent-dev-swarm.",
        "You do not have tool access in this runner.",
        "You did not edit files, run commands, or verify tests.",
        "Do not claim any file changes, command execution, or observed verification results that did not happen.",
        "Use the worker-result starter JSON as the base shape for your response.",
        "Return exactly one JSON object and no prose outside the JSON.",
        "Do not emit thinking text, markdown fences, or commentary before or after the JSON.",
        "Keep the result conservative. Status should normally remain 'partial' and verification_status should remain 'not_run'.",
        "Keep these fields as JSON arrays of strings: actions_performed, files_read, files_changed, commands_run, unresolved_issues, escalation_notes.",
        "Keep command_results as a JSON array of objects with command and outcome fields when entries are present.",
        "Keep required_outputs_status and success_criteria_status as arrays of objects with name and status fields.",
        "Allowed status values for required_outputs_status and success_criteria_status are: satisfied, missing, partial, not_evaluated.",
        "Do not change any field types from the starter payload.",
        f"Scenario: {scenario.scenario_id}",
        f"Description: {scenario.description}",
    ]
    if scenario.notes is not None:
        sections.append(f"Scenario notes: {scenario.notes}")
    sections.extend(
        [
            "WORKER HANDOFF JSON:",
            json.dumps(handoff_payload, indent=2),
            "WORKER RESULT STARTER JSON:",
            json.dumps(starter_payload, indent=2),
        ]
    )
    if context_sections:
        sections.append("WORKSPACE CONTEXT FILES:")
        sections.extend(context_sections)
    return "\n\n".join(sections) + "\n"


def _extract_worker_result_candidate(raw_output: str) -> dict[str, Any] | str:
    stripped = _sanitize_model_output(raw_output).strip()
    if not stripped:
        return "Local model returned empty output."

    direct = _try_parse_json(stripped)
    if isinstance(direct, dict):
        return direct

    fence_start = stripped.find("```")
    if fence_start != -1:
        fence_end = stripped.find("```", fence_start + 3)
        if fence_end != -1:
            fenced = stripped[fence_start + 3 : fence_end].strip()
            if fenced.startswith("json"):
                fenced = fenced[4:].strip()
            parsed_fenced = _try_parse_json(fenced)
            if isinstance(parsed_fenced, dict):
                return parsed_fenced

    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        parsed_substring = _try_parse_json(stripped[first_brace : last_brace + 1])
        if isinstance(parsed_substring, dict):
            return parsed_substring

    return "Could not extract a JSON worker result candidate from local model output."


def _sanitize_model_output(raw_output: str) -> str:
    sanitized = ANSI_ESCAPE_PATTERN.sub("", raw_output)
    return sanitized.replace("\r", "")


def _normalize_worker_result_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(payload))
    status_aliases = {
        "completed": "satisfied",
        "complete": "satisfied",
        "done": "satisfied",
        "pending": "not_evaluated",
        "not-run": "not_evaluated",
        "not_run": "not_evaluated",
        "todo": "not_evaluated",
    }
    for field_name in ("required_outputs_status", "success_criteria_status"):
        entries = normalized.get(field_name)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            status_value = entry.get("status")
            if isinstance(status_value, str):
                alias = status_aliases.get(status_value.strip().lower())
                if alias is not None:
                    entry["status"] = alias
    return normalized


def _try_parse_json(candidate: str) -> dict[str, Any] | str:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return str(exc)
    if not isinstance(parsed, dict):
        return "Parsed JSON value was not an object."
    return parsed


def _load_json_file(path: Path) -> dict[str, Any] | list[Any] | str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        return f"Failed to parse JSON file {path}: {exc}"
    except OSError as exc:
        return f"Failed to read JSON file {path}: {exc}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _normalize_non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    return normalized


def _normalize_relative_string_list(value: Any) -> list[str] | str:
    if not isinstance(value, list):
        return "must be a list of relative non-empty strings."
    normalized_items: list[str] = []
    for index, item in enumerate(value):
        normalized_item = _normalize_non_empty_string(item)
        if normalized_item is None:
            return f"contains an invalid entry at index {index}; each item must be a non-empty string."
        path_candidate = Path(normalized_item)
        if path_candidate.is_absolute() or any(part == ".." for part in path_candidate.parts):
            return f"contains an invalid relative path at index {index}: {normalized_item!r}."
        normalized_items.append(normalized_item)
    return normalized_items


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _coerce_stream_data(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _prefix_checks(prefix: str, checks: list[Any]) -> list[ScenarioCheck]:
    return [
        _check(f"{prefix}.{check.name}", check.status, check.message)
        for check in checks
    ]


def _check(name: str, status: str, message: str) -> ScenarioCheck:
    return ScenarioCheck(name=name, status=status, message=message)