from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re

FINAL_STATUSES = ("in_progress", "accept", "retry", "escalate")
VERIFICATION_STATUSES = ("not_run", "passed", "failed", "mixed")


@dataclass(slots=True)
class ImplementationRecordDraft:
    task_id: str
    title: str
    goal: str
    output_path: Path
    final_status: str = "in_progress"
    verification_status: str = "not_run"
    scope: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ImplementationRecordInitResult:
    status: str
    output_path: Path
    record_id: str
    task_id: str
    title: str
    final_status: str
    verification_status: str

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "output_path": str(self.output_path),
            "record_id": self.record_id,
            "task_id": self.task_id,
            "title": self.title,
            "final_status": self.final_status,
            "verification_status": self.verification_status,
        }


class ImplementationRecordError(ValueError):
    pass


def init_implementation_record(draft: ImplementationRecordDraft) -> ImplementationRecordInitResult:
    _validate_draft(draft)

    output_path = draft.output_path.expanduser().resolve()
    if output_path.exists():
        raise ImplementationRecordError(
            f"Implementation record already exists: {output_path}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    record_id = build_record_id(draft.task_id, draft.title)
    output_path.write_text(render_implementation_record(draft, record_id), encoding="utf-8")

    return ImplementationRecordInitResult(
        status="created",
        output_path=output_path,
        record_id=record_id,
        task_id=draft.task_id.strip(),
        title=draft.title.strip(),
        final_status=draft.final_status,
        verification_status=draft.verification_status,
    )


def build_record_id(task_id: str, title: str) -> str:
    normalized_task_id = _slugify(task_id.strip())
    normalized_title = _slugify(title.strip())
    if normalized_task_id and normalized_title:
        return f"{normalized_task_id}-{normalized_title}"
    return normalized_task_id or normalized_title or "implementation-record"


def format_implementation_record_init_summary(result: ImplementationRecordInitResult) -> str:
    return "\n".join(
        [
            "init-implementation-record: CREATED",
            f"output: {result.output_path}",
            f"record id: {result.record_id}",
            f"task id: {result.task_id}",
            f"verification status: {result.verification_status}",
            f"final status: {result.final_status}",
        ]
    )


def render_implementation_record(
    draft: ImplementationRecordDraft,
    record_id: str | None = None,
    created_at: datetime | None = None,
) -> str:
    timestamp = (created_at or datetime.now(timezone.utc)).replace(microsecond=0)
    timestamp_text = timestamp.isoformat().replace("+00:00", "Z")
    resolved_record_id = record_id or build_record_id(draft.task_id, draft.title)
    goal = draft.goal.strip() or "TODO: state the intended outcome of this bounded task."

    lines = [
        "# Implementation Record",
        "",
        f"- Record ID: {resolved_record_id}",
        f"- Task/Issue ID: {draft.task_id.strip()}",
        f"- Title: {draft.title.strip()}",
        f"- Created At (UTC): {timestamp_text}",
        f"- Updated At (UTC): {timestamp_text}",
        f"- Verification Status: {draft.verification_status}",
        f"- Final Status: {draft.final_status}",
        "",
        "## Goal",
        "",
        goal,
        "",
        "## Scope",
        "",
    ]
    lines.extend(_render_bullets(draft.scope, "TODO: define the intended boundary of this task."))
    lines.extend(
        [
            "",
            "## Non-Goals",
            "",
        ]
    )
    lines.extend(_render_bullets(draft.non_goals, "TODO: list the decisions or work that stay out of scope."))
    lines.extend(
        [
            "",
            "## Files Changed",
            "",
        ]
    )
    lines.extend(_render_bullets(draft.files_changed, "TODO: list changed files or note that no files changed yet."))
    lines.extend(
        [
            "",
            "## Structured Evidence",
            "",
        ]
    )
    lines.extend(
        _render_bullets(
            draft.evidence_refs,
            "TODO: reference saved JSON results or embed a short structured excerpt.",
        )
    )
    lines.extend(["", "## Commands Run", ""])
    lines.extend(_render_command_sections(draft.commands))
    lines.extend(
        [
            "",
            "## Observed Results",
            "",
            "- TODO: summarize what passed, failed, or changed.",
            "",
            "## Unresolved Issues",
            "",
            "- None.",
            "",
            "## Escalation Notes",
            "",
            "- None.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_bullets(items: list[str], placeholder: str) -> list[str]:
    cleaned_items = [item.strip() for item in items if item.strip()]
    if not cleaned_items:
        return [f"- {placeholder}"]
    return [f"- {item}" for item in cleaned_items]


def _render_command_sections(commands: list[str]) -> list[str]:
    cleaned_commands = [command.strip() for command in commands if command.strip()]
    if not cleaned_commands:
        cleaned_commands = ["TODO: add the first meaningful command for this task."]

    lines: list[str] = []
    for index, command in enumerate(cleaned_commands, start=1):
        if index > 1:
            lines.append("")
        lines.extend(
            [
                f"### Command {index}",
                "",
                f"- Command: {command}",
                "- Purpose: TODO",
                "- Outcome: TODO",
                "- Evidence: TODO",
            ]
        )
    return lines


def _slugify(value: str) -> str:
    collapsed = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return collapsed.strip("-")


def _validate_draft(draft: ImplementationRecordDraft) -> None:
    if not draft.task_id.strip():
        raise ImplementationRecordError("Task or issue identifier is required.")
    if not draft.title.strip():
        raise ImplementationRecordError("Record title is required.")
    if draft.final_status not in FINAL_STATUSES:
        raise ImplementationRecordError(
            "Final status must be one of: " + ", ".join(FINAL_STATUSES)
        )
    if draft.verification_status not in VERIFICATION_STATUSES:
        raise ImplementationRecordError(
            "Verification status must be one of: " + ", ".join(VERIFICATION_STATUSES)
        )